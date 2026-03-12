"""Tests for Phase 1 security hardening — logout, revocation, brute force, metrics, cookies."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestTokenRevocationAndLogout:
    """Verify that logout revokes tokens and subsequent requests fail."""

    async def _register_and_login(self, client: AsyncClient, email: str = "rev@example.com"):
        await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "Securepass123",
            "full_name": "Revoke User",
            "company_name": "RevokeCorp",
            "industry": "manufacturing",
            "region": "US",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "Securepass123",
        })
        data = resp.json()
        return data["access_token"], data.get("refresh_token")

    async def test_logout_revokes_access_token(self, client: AsyncClient):
        token, _ = await self._register_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}

        # Verify access works before logout
        resp = await client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200

        # Logout
        resp = await client.post("/api/v1/auth/logout", headers=headers)
        assert resp.status_code == 204

        # Access token should now be revoked
        resp = await client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 401

    async def test_logout_revokes_refresh_token(self, client: AsyncClient):
        token, refresh = await self._register_and_login(client, "refrev@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # Logout (revokes all refresh tokens)
        await client.post("/api/v1/auth/logout", headers=headers)

        # Refresh should fail
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 401

    async def test_refresh_token_rotation(self, client: AsyncClient):
        token, refresh = await self._register_and_login(client, "rot@example.com")

        # Exchange refresh token
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["refresh_token"] != refresh  # rotated

        # Old refresh token should be consumed (single use)
        resp2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert resp2.status_code == 401

    async def test_login_returns_csrf_token(self, client: AsyncClient):
        await self._register_and_login(client, "csrf@example.com")
        resp = await client.post("/api/v1/auth/login", json={
            "email": "csrf@example.com",
            "password": "Securepass123",
        })
        data = resp.json()
        assert "csrf_token" in data
        assert data["csrf_token"] is not None


@pytest.mark.asyncio
class TestBruteForceProtection:
    """Verify account lockout after repeated failed login attempts."""

    async def test_lockout_after_5_failures(self, client: AsyncClient):
        # Register a user
        await client.post("/api/v1/auth/register", json={
            "email": "brute@example.com",
            "password": "Securepass123",
            "full_name": "Brute User",
            "company_name": "BruteCorp",
            "industry": "manufacturing",
        })

        # Fail 5 times
        for i in range(5):
            resp = await client.post("/api/v1/auth/login", json={
                "email": "brute@example.com",
                "password": "WrongPassword1",
            })
            assert resp.status_code == 401, f"Attempt {i+1} expected 401"

        # 6th attempt should be locked out (429)
        resp = await client.post("/api/v1/auth/login", json={
            "email": "brute@example.com",
            "password": "WrongPassword1",
        })
        assert resp.status_code == 429

        # Even correct password should be blocked while locked
        resp = await client.post("/api/v1/auth/login", json={
            "email": "brute@example.com",
            "password": "Securepass123",
        })
        assert resp.status_code == 429

    async def test_successful_login_resets_attempts(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "reset@example.com",
            "password": "Securepass123",
            "full_name": "Reset User",
            "company_name": "ResetCorp",
            "industry": "energy",
        })

        # Fail 3 times (below threshold)
        for _ in range(3):
            await client.post("/api/v1/auth/login", json={
                "email": "reset@example.com",
                "password": "WrongPassword1",
            })

        # Success resets the counter
        resp = await client.post("/api/v1/auth/login", json={
            "email": "reset@example.com",
            "password": "Securepass123",
        })
        assert resp.status_code == 200

        # Now fail again — counter should be reset, so 3 failures won't lock
        for _ in range(3):
            await client.post("/api/v1/auth/login", json={
                "email": "reset@example.com",
                "password": "WrongPassword1",
            })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "reset@example.com",
            "password": "Securepass123",
        })
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestDeactivatedUser:
    """Verify deactivated accounts cannot access protected endpoints."""

    async def test_deactivated_user_denied(self, client: AsyncClient):
        # Register and login
        await client.post("/api/v1/auth/register", json={
            "email": "deact@example.com",
            "password": "Securepass123",
            "full_name": "Deactivated User",
            "company_name": "DeactCorp",
            "industry": "manufacturing",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "deact@example.com",
            "password": "Securepass123",
        })
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Deactivate user directly via DB
        from tests.conftest import TestSessionLocal
        from sqlalchemy import update
        from api.models import User

        async with TestSessionLocal() as session:
            await session.execute(update(User).where(User.email == "deact@example.com").values(is_active=False))
            await session.commit()

        # Should be rejected
        resp = await client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestMetricsEndpoint:
    """Verify the /metrics endpoint returns operational data."""

    async def test_metrics_returns_data(self, client: AsyncClient):
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        assert "total_requests" in data
        assert data["version"] == "0.7.0"
        assert data["total_requests"] >= 1


@pytest.mark.asyncio
class TestHealthEndpoint:
    """Verify health endpoint returns v0.7.0."""

    async def test_health_version(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["version"] == "0.7.0"
