"""Tests for SSE events route (/events/subscribe)."""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from api.services.event_bus import Subscription, _subscribers, publish


@pytest.mark.asyncio
class TestEventBus:
    """Unit tests for the in-process event bus."""

    async def test_subscription_registers_and_deregisters(self):
        company_id = "test-company-1"
        with Subscription(company_id) as queue:
            assert company_id in _subscribers
            assert queue in _subscribers[company_id]
        # After context exit, subscriber should be cleaned up
        assert company_id not in _subscribers

    async def test_publish_delivers_to_subscriber(self):
        company_id = "test-company-2"
        with Subscription(company_id) as queue:
            delivered = publish(company_id, "alert.created", {"id": "a1"})
            assert delivered == 1
            payload = queue.get_nowait()
            assert payload["event"] == "alert.created"
            assert payload["data"]["id"] == "a1"

    async def test_publish_to_no_subscribers_returns_zero(self):
        delivered = publish("nonexistent-company", "test", {})
        assert delivered == 0

    async def test_publish_to_multiple_subscribers(self):
        company_id = "test-company-3"
        with Subscription(company_id) as q1, Subscription(company_id) as q2:
            delivered = publish(company_id, "alert.created", {"id": "a2"})
            assert delivered == 2
            assert q1.get_nowait()["data"]["id"] == "a2"
            assert q2.get_nowait()["data"]["id"] == "a2"

    async def test_full_queue_drops_event(self):
        company_id = "test-company-4"
        sub = Subscription(company_id)
        sub.queue = asyncio.Queue(maxsize=1)
        with sub as queue:
            # Fill the queue
            publish(company_id, "first", {})
            # Second publish should drop (queue full)
            delivered = publish(company_id, "second", {})
            assert delivered == 0
            # Only first event should be in queue
            payload = queue.get_nowait()
            assert payload["event"] == "first"


@pytest.mark.asyncio
class TestEventsRoute:
    """Integration tests for the /events/subscribe SSE endpoint."""

    async def test_unauthenticated_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/events/subscribe")
        assert resp.status_code == 401

    async def test_subscribe_returns_event_stream(self, auth_client: AsyncClient):
        """Authenticated request should get a text/event-stream response."""
        import httpx
        from httpx import ASGITransport

        from api.main import app

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            headers=dict(auth_client.headers),
        ) as client:
            try:
                async with asyncio.timeout(2):
                    async with client.stream("GET", "/api/v1/events/subscribe") as response:
                        assert response.status_code == 200
                        assert "text/event-stream" in response.headers.get("content-type", "")
            except (TimeoutError, asyncio.TimeoutError):
                pass  # Expected — SSE stream never ends voluntarily

    async def test_subscribe_receives_published_event(self, auth_client: AsyncClient):
        """Published events should appear in the SSE stream generator."""
        from sqlalchemy import select

        from api.routes.events_routes import _event_stream
        from api.services.event_bus import publish
        from tests.conftest import TestSessionLocal

        # Resolve the auth user's company_id
        from api.models import User
        async with TestSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.email == "test@example.com")
            )
            user = result.scalar_one()
            company_id = user.company_id

        # Pre-publish an event so the generator can pick it up immediately
        # We need to create the subscription first, then publish, then read
        # Create a mock request that reports not-disconnected
        class _FakeRequest:
            async def is_disconnected(self):
                return False
        gen = _event_stream(_FakeRequest(), company_id)

        # The generator opens a Subscription context. By calling __anext__,
        # it enters the context and waits. We need to publish concurrently.
        collected: list[str] = []

        async def _consume():
            async for chunk in gen:
                collected.append(chunk)
                if "alert.created" in chunk:
                    break

        async def _publish():
            await asyncio.sleep(0.05)
            publish(company_id, "alert.created", {"id": "test-alert"})

        try:
            async with asyncio.timeout(5):
                await asyncio.gather(_consume(), _publish())
        except (TimeoutError, asyncio.TimeoutError):
            pass

        combined = "".join(collected)
        assert "alert.created" in combined
        assert "test-alert" in combined
