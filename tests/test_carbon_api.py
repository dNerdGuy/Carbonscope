"""Tests for carbon estimation and dashboard routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestEstimationRoute:
    async def test_estimate_creates_report(self, auth_client: AsyncClient):
        # First upload data
        upload_resp = await auth_client.post("/api/v1/data", json={
            "year": 2025,
            "provided_data": {
                "fuel_use_liters": 50_000,
                "fuel_type": "diesel",
                "electricity_kwh": 500_000,
                "employee_count": 100,
                "revenue_usd": 10_000_000,
                "supplier_spend_usd": 2_000_000,
            },
        })
        upload_id = upload_resp.json()["id"]

        # Run estimation
        resp = await auth_client.post("/api/v1/estimate", json={
            "data_upload_id": upload_id,
        })
        assert resp.status_code == 201
        report = resp.json()

        # Verify structure
        assert report["scope1"] > 0  # diesel fuel → Scope 1
        assert report["scope2"] > 0  # electricity → Scope 2
        assert report["scope3"] > 0  # supplier spend + employees → Scope 3
        assert report["total"] == pytest.approx(
            report["scope1"] + report["scope2"] + report["scope3"], rel=0.01
        )
        assert 0 < report["confidence"] <= 1.0
        assert report["year"] == 2025
        assert report["methodology_version"] == "ghg_protocol_v2025"

    async def test_estimate_minimal_data(self, auth_client: AsyncClient):
        upload_resp = await auth_client.post("/api/v1/data", json={
            "year": 2025,
            "provided_data": {"revenue_usd": 5_000_000},
        })
        upload_id = upload_resp.json()["id"]

        resp = await auth_client.post("/api/v1/estimate", json={
            "data_upload_id": upload_id,
        })
        assert resp.status_code == 201
        report = resp.json()
        # Low confidence for minimal data
        assert report["confidence"] < 0.5

    async def test_estimate_invalid_upload_id(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/estimate", json={
            "data_upload_id": "nonexistent",
        })
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestReportRoutes:
    async def _create_report(self, client: AsyncClient, year: int = 2025) -> dict:
        upload_resp = await client.post("/api/v1/data", json={
            "year": year,
            "provided_data": {
                "electricity_kwh": 100_000,
                "employee_count": 50,
            },
        })
        upload_id = upload_resp.json()["id"]
        resp = await client.post("/api/v1/estimate", json={"data_upload_id": upload_id})
        return resp.json()

    async def test_list_reports(self, auth_client: AsyncClient):
        await self._create_report(auth_client, 2024)
        await self._create_report(auth_client, 2025)

        resp = await auth_client.get("/api/v1/reports")
        assert resp.status_code == 200
        reports = resp.json()
        assert len(reports) == 2

    async def test_filter_reports_by_year(self, auth_client: AsyncClient):
        await self._create_report(auth_client, 2024)
        await self._create_report(auth_client, 2025)

        resp = await auth_client.get("/api/v1/reports?year=2025")
        reports = resp.json()
        assert all(r["year"] == 2025 for r in reports)

    async def test_get_report_by_id(self, auth_client: AsyncClient):
        report = await self._create_report(auth_client)
        report_id = report["id"]

        resp = await auth_client.get(f"/api/v1/reports/{report_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == report_id


@pytest.mark.asyncio
class TestDashboard:
    async def test_dashboard_empty(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["company"]["name"] == "TestCorp"
        assert data["reports_count"] == 0
        assert data["latest_report"] is None

    async def test_dashboard_with_data(self, auth_client: AsyncClient):
        # Create upload + report
        upload_resp = await auth_client.post("/api/v1/data", json={
            "year": 2025,
            "provided_data": {"electricity_kwh": 200_000, "employee_count": 80},
        })
        upload_id = upload_resp.json()["id"]
        await auth_client.post("/api/v1/estimate", json={"data_upload_id": upload_id})

        resp = await auth_client.get("/api/v1/dashboard")
        data = resp.json()
        assert data["reports_count"] == 1
        assert data["data_uploads_count"] == 1
        assert data["latest_report"] is not None
        assert data["latest_report"]["total"] > 0
        assert len(data["year_over_year"]) == 1


@pytest.mark.asyncio
class TestHealthCheck:
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
