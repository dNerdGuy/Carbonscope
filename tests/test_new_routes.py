"""Tests for new API routes: AI, supply chain, compliance, webhooks."""

import pytest
import pytest_asyncio
from httpx import AsyncClient


# ── Helper: create a report for tests ────────────────────────────────

async def _create_report(auth_client: AsyncClient) -> dict:
    """Upload data and create an estimate, return the report."""
    upload = await auth_client.post("/api/v1/data", json={
        "year": 2024,
        "provided_data": {
            "electricity_kwh": 300_000,
            "natural_gas_therms": 5000,
            "employee_count": 150,
            "revenue_usd": 20_000_000,
            "diesel_gallons": 2000,
        },
    })
    assert upload.status_code == 201
    upload_id = upload.json()["id"]
    resp = await auth_client.post("/api/v1/estimate", json={"data_upload_id": upload_id})
    assert resp.status_code == 201
    return resp.json()


# ── AI Routes ────────────────────────────────────────────────────────


class TestAIParseText:
    @pytest.mark.asyncio
    async def test_parse_text(self, auth_client):
        resp = await auth_client.post("/api/v1/ai/parse-text", json={
            "text": "We used 500,000 kWh of electricity and 3,000 therms of natural gas. Company has 200 employees."
        })
        assert resp.status_code == 200
        data = resp.json()["extracted_data"]
        assert data["electricity_kwh"] == 500_000
        assert data["natural_gas_therms"] == 3000
        assert data["employee_count"] == 200

    @pytest.mark.asyncio
    async def test_parse_empty_text(self, auth_client):
        resp = await auth_client.post("/api/v1/ai/parse-text", json={"text": "Nothing relevant."})
        assert resp.status_code == 200
        assert resp.json()["extracted_data"] == {}


class TestAIPredict:
    @pytest.mark.asyncio
    async def test_predict_with_known_data(self, auth_client):
        resp = await auth_client.post("/api/v1/ai/predict", json={
            "known_data": {"revenue_usd": 10_000_000, "employee_count": 100},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["method"] == "hybrid"
        assert "predictions" in data
        assert "uncertainty" in data

    @pytest.mark.asyncio
    async def test_predict_empty_data(self, auth_client):
        resp = await auth_client.post("/api/v1/ai/predict", json={
            "known_data": {},
        })
        assert resp.status_code == 200
        assert resp.json()["method"] == "industry_average"


class TestAIAuditTrail:
    @pytest.mark.asyncio
    async def test_audit_trail(self, auth_client):
        report = await _create_report(auth_client)
        resp = await auth_client.post("/api/v1/ai/audit-trail", json={
            "report_id": report["id"],
        })
        assert resp.status_code == 200
        assert "audit_trail" in resp.json()
        assert len(resp.json()["audit_trail"]) > 100

    @pytest.mark.asyncio
    async def test_audit_trail_not_found(self, auth_client):
        resp = await auth_client.post("/api/v1/ai/audit-trail", json={
            "report_id": "nonexistent",
        })
        assert resp.status_code == 404


class TestRecommendations:
    @pytest.mark.asyncio
    async def test_recommendations(self, auth_client):
        report = await _create_report(auth_client)
        resp = await auth_client.get(f"/api/v1/ai/recommendations/{report['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data
        assert "summary" in data
        assert data["summary"]["recommendation_count"] >= 0

    @pytest.mark.asyncio
    async def test_recommendations_not_found(self, auth_client):
        resp = await auth_client.get("/api/v1/ai/recommendations/nonexistent")
        assert resp.status_code == 404


# ── Compliance Routes ────────────────────────────────────────────────


class TestCompliance:
    @pytest.mark.asyncio
    async def test_ghg_protocol_report(self, auth_client):
        report = await _create_report(auth_client)
        resp = await auth_client.post("/api/v1/compliance/report", json={
            "report_id": report["id"],
            "framework": "ghg_protocol",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["framework"] == "GHG Protocol Corporate Standard"
        assert len(data["scope3_categories"]) == 15

    @pytest.mark.asyncio
    async def test_cdp_report(self, auth_client):
        report = await _create_report(auth_client)
        resp = await auth_client.post("/api/v1/compliance/report", json={
            "report_id": report["id"],
            "framework": "cdp",
        })
        assert resp.status_code == 200
        assert "modules" in resp.json()

    @pytest.mark.asyncio
    async def test_tcfd_report(self, auth_client):
        report = await _create_report(auth_client)
        resp = await auth_client.post("/api/v1/compliance/report", json={
            "report_id": report["id"],
            "framework": "tcfd",
        })
        assert resp.status_code == 200
        assert "pillars" in resp.json()

    @pytest.mark.asyncio
    async def test_sbti_pathway(self, auth_client):
        report = await _create_report(auth_client)
        resp = await auth_client.post("/api/v1/compliance/report", json={
            "report_id": report["id"],
            "framework": "sbti",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "pathway" in data
        assert len(data["pathway"]) == 11

    @pytest.mark.asyncio
    async def test_compliance_invalid_framework(self, auth_client):
        report = await _create_report(auth_client)
        resp = await auth_client.post("/api/v1/compliance/report", json={
            "report_id": report["id"],
            "framework": "invalid",
        })
        assert resp.status_code == 422


# ── Webhook Routes ───────────────────────────────────────────────────


class TestWebhooks:
    @pytest.mark.asyncio
    async def test_create_webhook(self, auth_client):
        resp = await auth_client.post("/api/v1/webhooks/", json={
            "url": "https://example.com/webhook",
            "event_types": ["report.created"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == "https://example.com/webhook"
        assert "secret" in data

    @pytest.mark.asyncio
    async def test_list_webhooks(self, auth_client):
        await auth_client.post("/api/v1/webhooks/", json={
            "url": "https://example.com/hook1",
            "event_types": ["report.created"],
        })
        resp = await auth_client.get("/api/v1/webhooks/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_toggle_webhook(self, auth_client):
        create_resp = await auth_client.post("/api/v1/webhooks/", json={
            "url": "https://example.com/hook",
            "event_types": ["data.uploaded"],
        })
        wh_id = create_resp.json()["id"]
        resp = await auth_client.patch(f"/api/v1/webhooks/{wh_id}?active=false")
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    @pytest.mark.asyncio
    async def test_delete_webhook(self, auth_client):
        create_resp = await auth_client.post("/api/v1/webhooks/", json={
            "url": "https://example.com/hook-del",
            "event_types": ["report.created"],
        })
        wh_id = create_resp.json()["id"]
        resp = await auth_client.delete(f"/api/v1/webhooks/{wh_id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_invalid_event_type(self, auth_client):
        resp = await auth_client.post("/api/v1/webhooks/", json={
            "url": "https://example.com/hook",
            "event_types": ["invalid.event"],
        })
        assert resp.status_code == 400
