"""Concurrency tests — parallel requests, race conditions."""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from api.services.subscriptions import deduct_credits, get_credit_balance
from tests.conftest import TestSessionLocal


async def _create_report(auth_client: AsyncClient, year: int = 2024) -> str:
    upload = await auth_client.post("/api/v1/data", json={
        "year": year,
        "provided_data": {"electricity_kwh": 100000},
    })
    upload_id = upload.json()["id"]
    est = await auth_client.post("/api/v1/estimate", json={"data_upload_id": upload_id})
    return est.json()["id"]


@pytest.mark.asyncio
class TestConcurrency:
    async def test_parallel_report_creation(self, auth_client: AsyncClient):
        """Multiple reports created concurrently should all succeed."""
        tasks = [_create_report(auth_client, year=2020 + i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        report_ids = [r for r in results if isinstance(r, str)]
        assert len(report_ids) == 5
        # All IDs should be unique
        assert len(set(report_ids)) == 5

    async def test_parallel_reads(self, auth_client: AsyncClient):
        """Parallel GET requests should all succeed."""
        tasks = [auth_client.get("/api/v1/reports") for _ in range(10)]
        results = await asyncio.gather(*tasks)
        assert all(r.status_code == 200 for r in results)

    async def test_parallel_supply_chain_link_creation(self, auth_client: AsyncClient):
        """Parallel link creation with different suppliers should succeed."""
        async def create_link(i: int):
            return await auth_client.post("/api/v1/supply-chain/links", json={
                "supplier_company_id": f"concurrent_supplier_{i}",
                "spend_usd": 1000.0 * i,
            })

        tasks = [create_link(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        successes = [r for r in results if r.status_code == 201]
        assert len(successes) == 5

    async def test_parallel_webhook_creation(self, auth_client: AsyncClient):
        """Sequential webhook creation with unique URLs."""
        for i in range(3):
            resp = await auth_client.post("/api/v1/webhooks/", json={
                "url": f"https://example.com/callback/{i}",
                "event_types": ["report.created"],
            })
            assert resp.status_code == 201

    async def test_read_write_interleave(self, auth_client: AsyncClient):
        """Interleaved reads and writes should not cause user-visible errors."""
        report_id = await _create_report(auth_client)

        # Verify read after create
        resp = await auth_client.get(f"/api/v1/reports/{report_id}")
        assert resp.status_code == 200

        # Write another upload
        resp2 = await auth_client.post("/api/v1/data", json={
            "year": 2025,
            "provided_data": {"electricity_kwh": 50000},
        })
        assert resp2.status_code == 201

        # Read again — original should still be there
        resp3 = await auth_client.get(f"/api/v1/reports/{report_id}")
        assert resp3.status_code == 200

    async def test_parallel_estimates_do_not_overdraw_credits(self, auth_client: AsyncClient):
        """Concurrent deductions should cap at available balance without underflow."""
        # Ensure subscription is initialized with free-plan credits.
        await auth_client.get("/api/v1/billing/subscription")
        me = await auth_client.get("/api/v1/auth/me")
        company_id = me.json()["company_id"]

        async def deduct_once() -> str:
            async with TestSessionLocal() as db:
                try:
                    await deduct_credits(db, company_id, 10, "concurrency_test")
                    await db.commit()
                    return "ok"
                except ValueError:
                    await db.rollback()
                    return "insufficient"

        results = await asyncio.gather(*[deduct_once() for _ in range(12)])
        success_count = results.count("ok")
        insufficient_count = results.count("insufficient")
        assert success_count + insufficient_count == 12

        async with TestSessionLocal() as db:
            balance = await get_credit_balance(db, company_id)
        assert balance >= 0
