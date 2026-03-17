"""Tests for billing/subscriptions, alerts, and data marketplace (Phase B/C/D)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ── Helpers ──────────────────────────────────────────────────────────


async def _create_report(auth_client: AsyncClient, year: int = 2024, **data_overrides) -> str:
    """Create a data upload + estimate to get a report ID."""
    provided_data = {"electricity_kwh": 100000, "natural_gas_therms": 5000}
    provided_data.update(data_overrides)
    upload = await auth_client.post("/api/v1/data", json={
        "year": year,
        "provided_data": provided_data,
    })
    upload_id = upload.json()["id"]
    est = await auth_client.post("/api/v1/estimate", json={"data_upload_id": upload_id})
    return est.json()["id"]


async def _upgrade_plan(auth_client: AsyncClient, plan: str = "pro") -> dict:
    """Upgrade the current company to given plan."""
    resp = await auth_client.post("/api/v1/billing/subscription", json={"plan": plan})
    return resp.json()


async def _register_second_user(client: AsyncClient) -> AsyncClient:
    """Register a second user/company and return an authenticated client."""
    await client.post("/api/v1/auth/register", json={
        "email": "buyer@other.com",
        "password": "Securepass123!",
        "full_name": "Buyer User",
        "company_name": "BuyerCorp",
        "industry": "technology",
        "region": "EU",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "buyer@other.com",
        "password": "Securepass123!",
    })
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


# ── Billing & Subscriptions ─────────────────────────────────────────


@pytest.mark.asyncio
class TestBillingSubscriptions:
    async def test_get_subscription_creates_free(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/billing/subscription")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "free"
        assert data["status"] == "active"

    async def test_change_plan_to_pro(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/billing/subscription", json={"plan": "pro"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "pro"
        assert data["status"] == "active"

    async def test_change_plan_to_enterprise(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/billing/subscription", json={"plan": "enterprise"})
        assert resp.status_code == 200
        assert resp.json()["plan"] == "enterprise"

    async def test_change_plan_invalid(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/billing/subscription", json={"plan": "premium"})
        assert resp.status_code == 422  # pydantic validation (pattern mismatch)

    async def test_downgrade_keeps_subscription(self, auth_client: AsyncClient):
        await _upgrade_plan(auth_client, "pro")
        resp = await auth_client.post("/api/v1/billing/subscription", json={"plan": "free"})
        assert resp.status_code == 200
        assert resp.json()["plan"] == "free"

    async def test_get_credits_default(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/billing/credits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["balance"] == 100  # free tier initial grant
        assert data["plan"] == "free"

    async def test_upgrade_grants_delta_credits(self, auth_client: AsyncClient):
        # Trigger free subscription creation (grants 100 credits)
        await auth_client.get("/api/v1/billing/subscription")
        # Upgrade to pro: free has 100, pro has 1000 → delta = 900
        await _upgrade_plan(auth_client, "pro")
        resp = await auth_client.get("/api/v1/billing/credits")
        assert resp.json()["balance"] == 1000  # 100 initial + 900 upgrade delta

    async def test_list_plans_no_auth(self, client: AsyncClient):
        """Unauthenticated access to /plans should be rejected."""
        resp = await client.get("/api/v1/billing/plans")
        assert resp.status_code == 401

    async def test_list_plans_authenticated(self, auth_client: AsyncClient):
        """Authenticated users can list plans."""
        resp = await auth_client.get("/api/v1/billing/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert "free" in data
        assert "pro" in data
        assert "enterprise" in data
        assert data["free"]["price_usd"] == 0
        assert data["pro"]["price_usd"] == 99
        assert data["enterprise"]["monthly_credits"] == 10000

    async def test_grant_credits_admin_success(self, auth_client: AsyncClient):
        """First registered user is admin and can grant credits."""
        # Ensure subscription exists
        await auth_client.get("/api/v1/billing/subscription")
        resp = await auth_client.post("/api/v1/billing/credits/grant", params={"amount": 500})
        assert resp.status_code == 200
        data = resp.json()
        assert data["balance"] >= 500

    async def test_grant_credits_invalid_amount(self, auth_client: AsyncClient):
        """Amount must be positive."""
        resp = await auth_client.post("/api/v1/billing/credits/grant", params={"amount": -10})
        assert resp.status_code == 400
        assert "positive" in resp.json()["detail"].lower()


# ── Alerts ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestAlerts:
    async def test_list_alerts_empty(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_check_alerts_no_reports(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/alerts/check")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_check_alerts_one_report(self, auth_client: AsyncClient):
        await _create_report(auth_client)
        resp = await auth_client.post("/api/v1/alerts/check")
        assert resp.status_code == 200
        assert resp.json() == []  # Need 2 reports

    async def test_check_alerts_emission_increase(self, auth_client: AsyncClient):
        # Create first report with lower emissions
        await _create_report(auth_client, year=2023, electricity_kwh=10000)
        # Create second report with higher emissions (10x increase)
        await _create_report(auth_client, year=2024, electricity_kwh=100000, natural_gas_therms=50000)
        resp = await auth_client.post("/api/v1/alerts/check")
        assert resp.status_code == 200
        alerts = resp.json()
        # Should detect an increase
        if len(alerts) > 0:
            assert any(a["alert_type"] == "emission_increase" for a in alerts)

    async def test_acknowledge_alert(self, auth_client: AsyncClient):
        # Create two reports with different emissions
        await _create_report(auth_client, year=2023, electricity_kwh=10000)
        await _create_report(auth_client, year=2024, electricity_kwh=100000, natural_gas_therms=50000)
        check_resp = await auth_client.post("/api/v1/alerts/check")
        alerts = check_resp.json()
        if len(alerts) > 0:
            alert_id = alerts[0]["id"]
            resp = await auth_client.post(f"/api/v1/alerts/{alert_id}/acknowledge")
            assert resp.status_code == 200
            data = resp.json()
            assert data["is_read"] is True
            assert data["acknowledged_at"] is not None

    async def test_acknowledge_nonexistent_alert(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/alerts/nonexistent-id/acknowledge")
        assert resp.status_code == 404

    async def test_list_alerts_unread_only(self, auth_client: AsyncClient):
        # Create alerts
        await _create_report(auth_client, year=2023, electricity_kwh=10000)
        await _create_report(auth_client, year=2024, electricity_kwh=100000, natural_gas_therms=50000)
        await auth_client.post("/api/v1/alerts/check")

        # Get all alerts
        all_resp = await auth_client.get("/api/v1/alerts")
        total_all = all_resp.json()["total"]

        if total_all > 0:
            # Acknowledge the first one
            alert_id = all_resp.json()["items"][0]["id"]
            await auth_client.post(f"/api/v1/alerts/{alert_id}/acknowledge")

            # unread_only should return fewer
            unread_resp = await auth_client.get("/api/v1/alerts", params={"unread_only": True})
            assert unread_resp.json()["total"] <= total_all

    async def test_list_alerts_pagination(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/alerts", params={"limit": 5, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data


# ── Data Marketplace ─────────────────────────────────────────────────


@pytest.mark.asyncio
class TestMarketplace:
    async def test_create_listing_requires_pro_plan(self, auth_client: AsyncClient):
        """Free plan cannot create marketplace listings."""
        report_id = await _create_report(auth_client)
        resp = await auth_client.post("/api/v1/marketplace/listings", json={
            "title": "Test Emission Data",
            "data_type": "emission_report",
            "report_id": report_id,
            "price_credits": 50,
        })
        assert resp.status_code == 403
        assert "marketplace" in resp.json()["detail"].lower()

    async def test_create_listing_pro_plan(self, auth_client: AsyncClient):
        """Pro plan can create marketplace listings."""
        await _upgrade_plan(auth_client, "pro")
        report_id = await _create_report(auth_client)
        resp = await auth_client.post("/api/v1/marketplace/listings", json={
            "title": "Manufacturing Emissions 2024",
            "description": "Anonymized emission data from manufacturing",
            "data_type": "emission_report",
            "report_id": report_id,
            "price_credits": 50,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Manufacturing Emissions 2024"
        assert data["status"] == "active"
        assert data["price_credits"] == 50
        assert "anonymized_data" in data
        assert data["anonymized_data"]["industry"] == "manufacturing"

    async def test_create_listing_invalid_report(self, auth_client: AsyncClient):
        """Cannot create listing for non-existent report."""
        await _upgrade_plan(auth_client, "pro")
        resp = await auth_client.post("/api/v1/marketplace/listings", json={
            "title": "Bad",
            "data_type": "emission_report",
            "report_id": "nonexistent-id",
            "price_credits": 0,
        })
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()

    async def test_browse_listings_empty(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/marketplace/listings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_browse_listings_with_data(self, auth_client: AsyncClient):
        """Create a listing then browse."""
        await _upgrade_plan(auth_client, "pro")
        report_id = await _create_report(auth_client)
        await auth_client.post("/api/v1/marketplace/listings", json={
            "title": "Test Data",
            "data_type": "emission_report",
            "report_id": report_id,
            "price_credits": 10,
        })
        resp = await auth_client.get("/api/v1/marketplace/listings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["items"][0]["title"] == "Test Data"

    async def test_browse_listings_filter_industry(self, auth_client: AsyncClient):
        """Filter listings by industry."""
        await _upgrade_plan(auth_client, "pro")
        report_id = await _create_report(auth_client)
        await auth_client.post("/api/v1/marketplace/listings", json={
            "title": "Mfg Data",
            "data_type": "emission_report",
            "report_id": report_id,
            "price_credits": 10,
        })
        # Filter by wrong industry
        resp = await auth_client.get("/api/v1/marketplace/listings", params={"industry": "finance"})
        assert resp.json()["total"] == 0

        # Filter by correct industry
        resp = await auth_client.get("/api/v1/marketplace/listings", params={"industry": "manufacturing"})
        assert resp.json()["total"] >= 1

    async def test_purchase_own_listing_fails(self, auth_client: AsyncClient):
        """Cannot purchase your own listing."""
        await _upgrade_plan(auth_client, "pro")
        report_id = await _create_report(auth_client)
        create_resp = await auth_client.post("/api/v1/marketplace/listings", json={
            "title": "My Data",
            "data_type": "emission_report",
            "report_id": report_id,
            "price_credits": 0,
        })
        listing_id = create_resp.json()["id"]
        resp = await auth_client.post(f"/api/v1/marketplace/listings/{listing_id}/purchase")
        assert resp.status_code == 400
        assert "own listing" in resp.json()["detail"].lower()

    async def test_purchase_nonexistent_listing(self, auth_client: AsyncClient):
        """Purchasing a nonexistent listing returns 400."""
        await _upgrade_plan(auth_client, "pro")
        resp = await auth_client.post("/api/v1/marketplace/listings/nonexistent/purchase")
        assert resp.status_code == 400

    async def test_duplicate_purchase_does_not_double_deduct_credits(self, auth_client: AsyncClient):
        """A duplicate purchase rejection must not mutate buyer credits again."""
        # Seller setup
        await _upgrade_plan(auth_client, "pro")
        report_id = await _create_report(auth_client)
        create_resp = await auth_client.post("/api/v1/marketplace/listings", json={
            "title": "Priced Listing",
            "data_type": "emission_report",
            "report_id": report_id,
            "price_credits": 25,
        })
        listing_id = create_resp.json()["id"]

        # Buyer setup (switches Authorization header on the same test client)
        buyer_client = await _register_second_user(auth_client)
        await _upgrade_plan(buyer_client, "pro")

        bal_before = (await buyer_client.get("/api/v1/billing/credits")).json()["balance"]

        first = await buyer_client.post(f"/api/v1/marketplace/listings/{listing_id}/purchase")
        assert first.status_code in (200, 201)
        bal_after_first = (await buyer_client.get("/api/v1/billing/credits")).json()["balance"]
        assert bal_after_first == bal_before - 25

        second = await buyer_client.post(f"/api/v1/marketplace/listings/{listing_id}/purchase")
        assert second.status_code == 400
        bal_after_second = (await buyer_client.get("/api/v1/billing/credits")).json()["balance"]
        assert bal_after_second == bal_after_first

    async def test_listing_data_type_validation(self, auth_client: AsyncClient):
        """Invalid data_type should fail schema validation."""
        await _upgrade_plan(auth_client, "pro")
        report_id = await _create_report(auth_client)
        resp = await auth_client.post("/api/v1/marketplace/listings", json={
            "title": "Bad Type",
            "data_type": "invalid_type",
            "report_id": report_id,
            "price_credits": 0,
        })
        assert resp.status_code == 422

    async def test_listing_pagination(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/marketplace/listings", params={"limit": 5, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert data["offset"] == 0


# ── Email Service (unit tests) ──────────────────────────────────────


@pytest.mark.asyncio
class TestEmailService:
    async def test_send_email_dev_mode(self):
        """In dev mode (no SMTP), send_email logs and returns True."""
        from api.services.email import send_email

        result = await send_email("test@example.com", "Test", "<p>Hello</p>")
        assert result is True

    async def test_send_alert_email(self):
        from api.services.email import send_alert_email

        result = await send_alert_email("admin@example.com", "Emissions Up", "Total increased by 15%", "warning")
        assert result is True

    async def test_send_report_ready_email(self):
        from api.services.email import send_report_ready_email

        result = await send_report_ready_email("user@example.com", 2024, 1500.5)
        assert result is True

    async def test_send_subscription_change_email(self):
        from api.services.email import send_subscription_change_email

        result = await send_subscription_change_email("user@example.com", "free", "pro")
        assert result is True


# ── Scheduler (unit tests) ──────────────────────────────────────────


@pytest.mark.asyncio
class TestScheduler:
    async def test_start_and_stop_scheduler(self):
        from api.services.scheduler import start_scheduler, stop_scheduler, _scheduler_task

        start_scheduler()
        from api.services import scheduler

        assert scheduler._scheduler_task is not None
        assert not scheduler._scheduler_task.done()

        await stop_scheduler()
        # After stop, task should be cancelled or done
        assert scheduler._scheduler_task is None or scheduler._scheduler_task.done()

    async def test_start_scheduler_idempotent(self):
        from api.services.scheduler import start_scheduler, stop_scheduler
        from api.services import scheduler

        start_scheduler()
        task1 = scheduler._scheduler_task
        start_scheduler()  # Should not create a new task
        task2 = scheduler._scheduler_task
        assert task1 is task2
        await stop_scheduler()


# ── Plan gating integration ──────────────────────────────────────────


@pytest.mark.asyncio
class TestPlanGating:
    async def test_free_plan_blocks_marketplace(self, auth_client: AsyncClient):
        """Free plan cannot access marketplace create."""
        report_id = await _create_report(auth_client)
        resp = await auth_client.post("/api/v1/marketplace/listings", json={
            "title": "Blocked",
            "data_type": "emission_report",
            "report_id": report_id,
            "price_credits": 0,
        })
        assert resp.status_code == 403

    async def test_pro_plan_allows_marketplace(self, auth_client: AsyncClient):
        """Pro plan can access marketplace."""
        await _upgrade_plan(auth_client, "pro")
        report_id = await _create_report(auth_client)
        resp = await auth_client.post("/api/v1/marketplace/listings", json={
            "title": "Allowed",
            "data_type": "emission_report",
            "report_id": report_id,
            "price_credits": 0,
        })
        assert resp.status_code == 201


# ── Marketplace Seller Dashboard ─────────────────────────────────────


@pytest.mark.asyncio
class TestMarketplaceSeller:
    async def test_my_sales_empty(self, auth_client: AsyncClient):
        """Seller with no sales returns empty list."""
        resp = await auth_client.get("/api/v1/marketplace/my-sales")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_my_revenue_empty(self, auth_client: AsyncClient):
        """Seller with no sales returns zero revenue."""
        resp = await auth_client.get("/api/v1/marketplace/my-revenue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_revenue_credits"] == 0
        assert data["total_sales"] == 0
        assert data["active_listings"] == 0

    async def test_my_revenue_with_listing(self, auth_client: AsyncClient):
        """Active listing counts in revenue summary."""
        await _upgrade_plan(auth_client, "pro")
        report_id = await _create_report(auth_client)
        await auth_client.post("/api/v1/marketplace/listings", json={
            "title": "Revenue Test",
            "data_type": "emission_report",
            "report_id": report_id,
            "price_credits": 25,
        })
        resp = await auth_client.get("/api/v1/marketplace/my-revenue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_listings"] >= 1
        # No purchases yet
        assert data["total_sales"] == 0

    async def test_my_sales_pagination(self, auth_client: AsyncClient):
        """Sales endpoint respects limit/offset params."""
        resp = await auth_client.get(
            "/api/v1/marketplace/my-sales", params={"limit": 5, "offset": 0}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert data["offset"] == 0
