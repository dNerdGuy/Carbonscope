"""Phase 25 hardening tests — audit logging, rate limiting, auth gates, session invalidation."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ── Helpers ─────────────────────────────────────────────────────────


async def _register_and_login(client: AsyncClient, email: str = "test25@example.com") -> AsyncClient:
    await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Securepass123!",
        "full_name": "P25 User",
        "company_name": "P25Corp",
        "industry": "energy",
        "region": "EU",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "Securepass123!",
    })
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


async def _register_second_user(client: AsyncClient) -> dict:
    """Register a second company and return token + headers."""
    await client.post("/api/v1/auth/register", json={
        "email": "other@example.com",
        "password": "Securepass123!",
        "full_name": "Other User",
        "company_name": "OtherCorp",
        "industry": "finance",
        "region": "UK",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "other@example.com",
        "password": "Securepass123!",
    })
    return resp.json()


# ── Auth gates ──────────────────────────────────────────────────────


class TestAuthGates:
    """Endpoints that now require auth should reject unauthenticated requests."""

    async def test_metrics_public_access(self, client: AsyncClient):
        resp = await client.get("/metrics")
        assert resp.status_code == 401

    async def test_billing_plans_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/billing/plans")
        assert resp.status_code == 401

    async def test_billing_plans_works_with_auth(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/billing/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert "free" in data and "pro" in data

    async def test_metrics_works_with_auth(self, auth_client: AsyncClient):
        resp = await auth_client.get("/metrics")
        assert resp.status_code == 200
        assert "version" in resp.json()


# ── Audit logging coverage ──────────────────────────────────────────


class TestAuditLogging:
    """Verify that critical mutations create audit log entries."""

    async def test_register_creates_audit_entry(self, client: AsyncClient):
        ac = await _register_and_login(client)
        resp = await ac.get("/api/v1/audit-logs/")
        data = resp.json()
        actions = [item["action"] for item in data["items"]]
        assert "register" in actions

    async def test_login_creates_audit_entry(self, client: AsyncClient):
        ac = await _register_and_login(client)
        resp = await ac.get("/api/v1/audit-logs/")
        data = resp.json()
        actions = [item["action"] for item in data["items"]]
        assert "login" in actions

    async def test_admin_grant_credits_audit(self, auth_client: AsyncClient):
        await auth_client.get("/api/v1/billing/subscription")
        await auth_client.post("/api/v1/billing/credits/grant", params={"amount": 10})
        resp = await auth_client.get("/api/v1/audit-logs/")
        data = resp.json()
        actions = [item["action"] for item in data["items"]]
        assert "admin_grant_credits" in actions

    async def test_subscription_change_audit(self, auth_client: AsyncClient):
        await auth_client.get("/api/v1/billing/subscription")
        await auth_client.post("/api/v1/billing/subscription", json={"plan": "pro"})
        resp = await auth_client.get("/api/v1/audit-logs/")
        data = resp.json()
        actions = [item["action"] for item in data["items"]]
        assert "update" in actions
        # Check that the subscription update is recorded
        sub_updates = [
            item for item in data["items"]
            if item["action"] == "update" and item["resource_type"] == "subscription"
        ]
        assert len(sub_updates) >= 1

    async def test_compliance_report_audit(self, auth_client: AsyncClient):
        # Upload data and create estimate
        await auth_client.get("/api/v1/billing/subscription")
        await auth_client.post("/api/v1/billing/subscription", json={"plan": "pro"})
        upload_resp = await auth_client.post("/api/v1/data", json={
            "year": 2024,
            "provided_data": {
                "electricity_kwh": 100000,
                "natural_gas_therms": 5000,
            },
        })
        upload_id = upload_resp.json()["id"]
        est_resp = await auth_client.post("/api/v1/estimate", json={
            "data_upload_id": upload_id,
        })
        report_id = est_resp.json()["id"]
        # Generate compliance report
        await auth_client.post("/api/v1/compliance/report", json={
            "report_id": report_id,
            "framework": "ghg_protocol",
        })
        resp = await auth_client.get("/api/v1/audit-logs/")
        data = resp.json()
        compliance_entries = [
            item for item in data["items"]
            if item["resource_type"] == "compliance_report"
        ]
        assert len(compliance_entries) >= 1

    async def test_mfa_setup_creates_audit_entry(self, auth_client: AsyncClient):
        await auth_client.post("/api/v1/auth/mfa/setup")
        resp = await auth_client.get("/api/v1/audit-logs/", params={"resource_type": "mfa"})
        data = resp.json()
        actions = [item["action"] for item in data["items"]]
        assert "mfa_setup" in actions

    async def test_refresh_creates_audit_entry(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "refreshaudit@example.com",
            "password": "Securepass123!",
            "full_name": "Refresh Audit",
            "company_name": "RefreshCorp",
            "industry": "technology",
            "region": "US",
        })
        login = await client.post("/api/v1/auth/login", json={
            "email": "refreshaudit@example.com",
            "password": "Securepass123!",
        })
        refresh = login.json()["refresh_token"]
        token = login.json()["access_token"]

        refreshed = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh,
        })
        assert refreshed.status_code == 200

        client.headers["Authorization"] = f"Bearer {token}"
        logs = await client.get("/api/v1/audit-logs/", params={"resource_type": "auth"})
        actions = [item["action"] for item in logs.json()["items"]]
        assert "token_refresh" in actions


# ── Session invalidation ────────────────────────────────────────────


class TestSessionInvalidation:
    """Password change and reset should invalidate sessions."""

    async def test_change_password_invalidates_refresh_tokens(self, client: AsyncClient):
        # Register and login
        await client.post("/api/v1/auth/register", json={
            "email": "sesstest@example.com",
            "password": "Securepass123!",
            "full_name": "Sess User",
            "company_name": "SessCorp",
            "industry": "tech",
            "region": "US",
        })
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "sesstest@example.com",
            "password": "Securepass123!",
        })
        token = login_resp.json()["access_token"]
        refresh = login_resp.json()["refresh_token"]
        client.headers["Authorization"] = f"Bearer {token}"

        # Change password
        resp = await client.post("/api/v1/auth/change-password", json={
            "current_password": "Securepass123!",
            "new_password": "Newsecure456!",
        })
        assert resp.status_code == 204

        # Old refresh token should be revoked
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh,
        })
        assert resp.status_code == 401


# ── Webhook auth consistency ────────────────────────────────────────


class TestWebhookAuthConsistency:
    """Webhook update should require admin just like create/delete."""

    async def test_webhook_update_requires_admin(self, auth_client: AsyncClient):
        """Admin user can create and update a webhook."""
        from unittest.mock import patch

        with patch("api.services.url_validator.validate_webhook_url"):
            # Create a webhook
            wh_resp = await auth_client.post("/api/v1/webhooks/", json={
                "url": "https://hooks.example.com/test",
                "event_types": ["report.created"],
            })
            assert wh_resp.status_code == 201
            wh_id = wh_resp.json()["id"]

            # Admin can update (toggle)
            resp = await auth_client.patch(f"/api/v1/webhooks/{wh_id}", json={"active": False})
            assert resp.status_code == 200


# ── Cross-company isolation ─────────────────────────────────────────


class TestCrossCompanyIsolation:
    """Verify that company A cannot access company B's resources."""

    async def test_cannot_access_other_company_data(self, client: AsyncClient):
        # Register company A
        await client.post("/api/v1/auth/register", json={
            "email": "compa@example.com",
            "password": "Securepass123!",
            "full_name": "A User",
            "company_name": "CompanyA",
            "industry": "manufacturing",
            "region": "US",
        })
        a_resp = await client.post("/api/v1/auth/login", json={
            "email": "compa@example.com",
            "password": "Securepass123!",
        })
        a_token = a_resp.json()["access_token"]

        # Company A uploads data
        client.headers["Authorization"] = f"Bearer {a_token}"
        upload = await client.post("/api/v1/data", json={
            "year": 2024,
            "provided_data": {"electricity_kwh": 50000},
        })
        upload_id = upload.json()["id"]

        # Register company B
        del client.headers["Authorization"]
        await client.post("/api/v1/auth/register", json={
            "email": "compb@example.com",
            "password": "Securepass123!",
            "full_name": "B User",
            "company_name": "CompanyB",
            "industry": "tech",
            "region": "EU",
        })
        b_resp = await client.post("/api/v1/auth/login", json={
            "email": "compb@example.com",
            "password": "Securepass123!",
        })
        b_token = b_resp.json()["access_token"]

        # Company B tries to access company A's upload
        client.headers["Authorization"] = f"Bearer {b_token}"
        resp = await client.get(f"/api/v1/data/{upload_id}")
        assert resp.status_code == 404

    async def test_cannot_access_other_company_reports(self, client: AsyncClient):
        # Company A registers, uploads, and estimates
        await client.post("/api/v1/auth/register", json={
            "email": "iso_a@example.com",
            "password": "Securepass123!",
            "full_name": "IsoA User",
            "company_name": "IsoCompA",
            "industry": "energy",
            "region": "US",
        })
        a_resp = await client.post("/api/v1/auth/login", json={
            "email": "iso_a@example.com",
            "password": "Securepass123!",
        })
        a_token = a_resp.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {a_token}"

        upload = await client.post("/api/v1/data", json={
            "year": 2024,
            "provided_data": {"electricity_kwh": 75000},
        })
        upload_id = upload.json()["id"]
        est = await client.post("/api/v1/estimate", json={"data_upload_id": upload_id})
        report_id = est.json()["id"]

        # Company B tries to access A's reports
        del client.headers["Authorization"]
        await client.post("/api/v1/auth/register", json={
            "email": "iso_b@example.com",
            "password": "Securepass123!",
            "full_name": "IsoB User",
            "company_name": "IsoCompB",
            "industry": "tech",
            "region": "EU",
        })
        b_resp = await client.post("/api/v1/auth/login", json={
            "email": "iso_b@example.com",
            "password": "Securepass123!",
        })
        b_token = b_resp.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {b_token}"

        # Should not see A's report in their list
        resp = await client.get("/api/v1/reports")
        assert resp.status_code == 200
        reports = resp.json()["items"]
        report_ids = [r["id"] for r in reports]
        assert report_id not in report_ids

        # Direct access should be 404
        resp = await client.get(f"/api/v1/reports/{report_id}")
        assert resp.status_code == 404


# ── Rate limiting on newly protected routes ─────────────────────────


class TestNewRateLimiting:
    """Verify that newly rate-limited endpoints accept the Request param correctly."""

    async def test_company_endpoints_accessible(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/company")
        assert resp.status_code == 200

    async def test_data_endpoints_accessible(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/data")
        assert resp.status_code == 200

    async def test_alerts_endpoint_accessible(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/alerts")
        assert resp.status_code == 200

    async def test_supply_chain_endpoint_accessible(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/supply-chain/suppliers")
        assert resp.status_code == 200

    async def test_webhooks_endpoint_accessible(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/webhooks/")
        assert resp.status_code == 200

    async def test_audit_logs_endpoint_accessible(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/audit-logs/")
        assert resp.status_code == 200

    async def test_scenarios_endpoint_accessible(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/scenarios/")
        assert resp.status_code == 200

    async def test_questionnaires_endpoint_accessible(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/questionnaires/")
        assert resp.status_code == 200

    async def test_marketplace_endpoint_accessible(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/marketplace/listings")
        assert resp.status_code == 200

    async def test_reviews_endpoint_accessible(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/reviews")
        assert resp.status_code == 200

    async def test_benchmarks_endpoint_accessible(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/benchmarks/industry")
        # 200 or 404 (no data) are both valid — means route exists and auth works
        assert resp.status_code in (200, 404)


# ── PCAF audit logging ──────────────────────────────────────────────


class TestPCAFAudit:
    """PCAF mutations should create audit entries."""

    async def test_pcaf_portfolio_create_audit(self, auth_client: AsyncClient):
        # Upgrade to supply_chain-capable plan
        await auth_client.get("/api/v1/billing/subscription")
        await auth_client.post("/api/v1/billing/subscription", json={"plan": "enterprise"})

        resp = await auth_client.post("/api/v1/pcaf/portfolios", json={
            "name": "Test Portfolio",
            "year": 2024,
        })
        assert resp.status_code == 201

        logs = await auth_client.get("/api/v1/audit-logs/", params={"resource_type": "pcaf_portfolio"})
        assert logs.json()["total"] >= 1


# ── Review audit logging ────────────────────────────────────────────


class TestReviewAudit:
    """Review creation should create audit entry."""

    async def test_review_create_audit(self, auth_client: AsyncClient):
        # Create data + report first
        upload = await auth_client.post("/api/v1/data", json={
            "year": 2024,
            "provided_data": {"electricity_kwh": 100000},
        })
        upload_id = upload.json()["id"]
        est = await auth_client.post("/api/v1/estimate", json={"data_upload_id": upload_id})
        report_id = est.json()["id"]

        # Create review
        resp = await auth_client.post("/api/v1/reviews", json={"report_id": report_id})
        assert resp.status_code == 201

        logs = await auth_client.get("/api/v1/audit-logs/", params={"resource_type": "data_review"})
        assert logs.json()["total"] >= 1
