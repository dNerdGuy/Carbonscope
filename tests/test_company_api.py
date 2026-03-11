"""Tests for company and data upload routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestCompanyRoutes:
    async def test_get_company(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/company")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "TestCorp"
        assert data["industry"] == "manufacturing"

    async def test_update_company(self, auth_client: AsyncClient):
        resp = await auth_client.patch("/api/v1/company", json={
            "employee_count": 150,
            "revenue_usd": 25_000_000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["employee_count"] == 150
        assert data["revenue_usd"] == 25_000_000
        # Unchanged fields remain
        assert data["name"] == "TestCorp"

    async def test_unauthenticated_rejected(self, client: AsyncClient):
        resp = await client.get("/api/v1/company")
        assert resp.status_code in (401, 403)  # no bearer token


@pytest.mark.asyncio
class TestDataUploadRoutes:
    async def test_upload_data(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/data", json={
            "year": 2025,
            "provided_data": {
                "fuel_use_liters": 50_000,
                "fuel_type": "diesel",
                "electricity_kwh": 500_000,
                "employee_count": 100,
            },
            "notes": "Annual report data",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["year"] == 2025
        assert data["provided_data"]["fuel_use_liters"] == 50_000
        assert "id" in data

    async def test_list_uploads(self, auth_client: AsyncClient):
        # Create two uploads
        await auth_client.post("/api/v1/data", json={
            "year": 2024,
            "provided_data": {"electricity_kwh": 100_000},
        })
        await auth_client.post("/api/v1/data", json={
            "year": 2025,
            "provided_data": {"electricity_kwh": 200_000},
        })

        resp = await auth_client.get("/api/v1/data")
        assert resp.status_code == 200
        uploads = resp.json()
        assert len(uploads) == 2
        # Should be ordered by year desc
        assert uploads[0]["year"] >= uploads[1]["year"]

    async def test_get_upload_by_id(self, auth_client: AsyncClient):
        create_resp = await auth_client.post("/api/v1/data", json={
            "year": 2025,
            "provided_data": {"fuel_use_liters": 10_000},
        })
        upload_id = create_resp.json()["id"]

        resp = await auth_client.get(f"/api/v1/data/{upload_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == upload_id

    async def test_get_nonexistent_upload(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/data/nonexistent")
        assert resp.status_code == 404
