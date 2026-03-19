"""Phase 21D — Additional test coverage.

Tests for:
 - Webhook retry exhaustion
 - Marketplace email failure resilience
 - LLM extraction fallback
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Company, Webhook, WebhookDelivery
from tests.conftest import TestSessionLocal


# ── Helpers ──────────────────────────────────────────────────────────

async def _get_db_session() -> AsyncSession:
    async with TestSessionLocal() as s:
        return s


async def _seed_webhook(db: AsyncSession) -> tuple[Company, Webhook]:
    company = Company(name="RetryTestCorp", industry="technology", region="US")
    db.add(company)
    await db.flush()

    wh = Webhook(
        company_id=company.id,
        url="https://example.com/hook",
        event_types=["report.created"],
        secret="test-secret-key",
        active=True,
    )
    db.add(wh)
    await db.flush()
    return company, wh


# ── Webhook retry exhaustion ────────────────────────────────────────

@pytest.mark.asyncio
class TestWebhookRetryExhaustion:
    """Verify that webhook deliveries stop retrying after max_retries."""

    async def test_retry_exhaustion_clears_next_retry(self):
        """When retry_count reaches max_retries, next_retry_at should be set to None."""
        async with TestSessionLocal() as db:
            _company, wh = await _seed_webhook(db)

            delivery = WebhookDelivery(
                webhook_id=wh.id,
                event_type="report.created",
                payload={"test": True},
                success=False,
                retry_count=2,       # one below max_retries (3)
                max_retries=3,
                next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=10),
            )
            db.add(delivery)
            await db.commit()
            delivery_id = delivery.id

            # Mock httpx to keep failing
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.text = "Internal Server Error"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            with patch("api.services.webhooks.httpx.AsyncClient", return_value=mock_client):
                from api.services.webhooks import process_pending_retries
                processed = await process_pending_retries(db)

            assert processed == 1

            # Reload and check
            result = await db.execute(
                select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
            )
            d = result.scalar_one()
            assert d.retry_count == 3
            assert d.next_retry_at is None  # exhausted — no more retries
            assert d.success is False

    async def test_retry_schedules_next_when_under_max(self):
        """When retry_count < max_retries, next_retry_at should be set to a future time."""
        async with TestSessionLocal() as db:
            _company, wh = await _seed_webhook(db)

            delivery = WebhookDelivery(
                webhook_id=wh.id,
                event_type="report.created",
                payload={"test": True},
                success=False,
                retry_count=0,       # plenty of retries left
                max_retries=3,
                next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=10),
            )
            db.add(delivery)
            await db.commit()
            delivery_id = delivery.id

            mock_resp = MagicMock()
            mock_resp.status_code = 502
            mock_resp.text = "Bad Gateway"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            with patch("api.services.webhooks.httpx.AsyncClient", return_value=mock_client):
                from api.services.webhooks import process_pending_retries
                processed = await process_pending_retries(db)

            assert processed == 1

            result = await db.execute(
                select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
            )
            d = result.scalar_one()
            assert d.retry_count == 1
            assert d.next_retry_at is not None  # should be scheduled for later
            assert d.next_retry_at > datetime.now(timezone.utc)

    async def test_retry_success_clears_retry_at(self):
        """On successful retry, next_retry_at and success should be updated."""
        async with TestSessionLocal() as db:
            _company, wh = await _seed_webhook(db)

            delivery = WebhookDelivery(
                webhook_id=wh.id,
                event_type="report.created",
                payload={"event": "report.created"},
                success=False,
                retry_count=1,
                max_retries=3,
                next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=5),
            )
            db.add(delivery)
            await db.commit()
            delivery_id = delivery.id

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "OK"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            with patch("api.services.webhooks.httpx.AsyncClient", return_value=mock_client):
                from api.services.webhooks import process_pending_retries
                processed = await process_pending_retries(db)

            assert processed == 1

            result = await db.execute(
                select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
            )
            d = result.scalar_one()
            assert d.success is True
            assert d.next_retry_at is None
            assert d.retry_count == 2

    async def test_inactive_webhook_stops_retries(self):
        """Deliveries for deactivated webhooks should stop retrying."""
        async with TestSessionLocal() as db:
            _company, wh = await _seed_webhook(db)
            wh.active = False
            await db.flush()

            delivery = WebhookDelivery(
                webhook_id=wh.id,
                event_type="report.created",
                payload={"test": True},
                success=False,
                retry_count=0,
                max_retries=3,
                next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=10),
            )
            db.add(delivery)
            await db.commit()
            delivery_id = delivery.id

            from api.services.webhooks import process_pending_retries
            await process_pending_retries(db)

            result = await db.execute(
                select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
            )
            d = result.scalar_one()
            assert d.next_retry_at is None  # stopped
            assert d.retry_count == 0       # never tried


# ── Marketplace email failure resilience ────────────────────────────

@pytest.mark.asyncio
class TestMarketplaceEmailResilience:
    """Verify purchase succeeds even when email notifications fail."""

    async def test_purchase_succeeds_when_email_raises(self, auth_client: AsyncClient):
        """Purchase should succeed even when email sending raises."""
        # Set up: create a separate seller company + listing directly in DB
        async with TestSessionLocal() as db:
            from api.models import DataListing, Subscription, CreditLedger

            # Create seller company
            seller_co = Company(name="SellerCorp", industry="retail", region="US")
            db.add(seller_co)
            await db.flush()

            listing = DataListing(
                seller_company_id=seller_co.id,
                title="Retail Emissions 2024",
                description="Anonymized retail data",
                data_type="emission_report",
                industry="retail",
                region="US",
                year=2024,
                price_credits=0,  # free to avoid credit balance issues
                anonymized_data={"scope1": 100},
                status="active",
            )
            db.add(listing)
            await db.flush()
            listing_id = listing.id

            # Give buyer an enterprise subscription so require_plan("marketplace") passes
            # First find the buyer's company_id
            from api.models import User as UserModel
            result = await db.execute(
                select(UserModel).where(UserModel.email == "test@example.com")
            )
            buyer = result.scalar_one()

            # Update existing subscription to enterprise (registration creates a free one)
            sub_result = await db.execute(
                select(Subscription).where(Subscription.company_id == buyer.company_id)
            )
            sub = sub_result.scalar_one_or_none()
            if sub:
                sub.plan = "enterprise"
                sub.status = "active"
            else:
                sub = Subscription(
                    company_id=buyer.company_id,
                    plan="enterprise",
                    status="active",
                )
                db.add(sub)
            await db.commit()

        # Mock email to raise, then purchase
        with patch("api.routes.marketplace_routes.send_marketplace_purchase_email",
                    side_effect=Exception("SMTP failed"), create=True), \
             patch("api.routes.marketplace_routes.send_marketplace_sale_email",
                    side_effect=Exception("SMTP failed"), create=True):
            resp = await auth_client.post(f"/api/v1/marketplace/listings/{listing_id}/purchase")

        # Purchase should succeed (the email failure is caught in the route)
        assert resp.status_code in (200, 201)


# ── LLM extraction fallback ────────────────────────────────────────

@pytest.mark.asyncio
class TestLLMExtractionFallback:
    """Verify LLM parser falls back to rule-based extraction on failure."""

    async def test_fallback_on_llm_exception(self):
        """When LLM client raises, should return rule-based results."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("API key invalid")
        mock_client.chat.completions.create.side_effect = RuntimeError("API key invalid")

        with patch("api.services.llm_parser._get_llm_client", return_value=mock_client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            from api.services.llm_parser import parse_unstructured_text
            result = await parse_unstructured_text("We used 5000 kWh of electricity and 200 therms of natural gas")

        assert "electricity_kwh" in result
        assert result["electricity_kwh"] == 5000.0
        assert "natural_gas_therms" in result
        assert result["natural_gas_therms"] == 200.0

    async def test_fallback_when_no_api_key(self):
        """When no LLM client is available, should use rule-based extraction."""
        with patch("api.services.llm_parser._get_llm_client", return_value=None):
            from api.services.llm_parser import parse_unstructured_text
            result = await parse_unstructured_text("Fleet of 10000 miles driven, 500 gallons of diesel")

        assert "fleet_miles" in result
        assert result["fleet_miles"] == 10000.0
        assert "diesel_gallons" in result
        assert result["diesel_gallons"] == 500.0

    async def test_fallback_on_json_parse_error(self):
        """When LLM returns invalid JSON, should fall back to rule-based."""
        mock_client = MagicMock()
        # Simulate LLM returning garbage
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is not JSON at all")]
        mock_client.messages.create.return_value = mock_response

        with patch("api.services.llm_parser._get_llm_client", return_value=mock_client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            from api.services.llm_parser import parse_unstructured_text
            result = await parse_unstructured_text("Used 1500 kWh of electricity")

        # Should get rule-based result (the json.loads will fail on the garbage text,
        # triggering the except block)
        assert "electricity_kwh" in result
        assert result["electricity_kwh"] == 1500.0

    def test_rule_based_extraction_accuracy(self):
        """Verify rule-based extraction works correctly for various units."""
        from api.services.llm_parser import parse_text_rule_based

        result = parse_text_rule_based(
            "Company used 2.5 MWh of electricity, 100 gallons of gasoline, "
            "revenue of $5.2 million, and 15 metric tons of waste. "
            "They have 250 employees and 1000 ton-miles of freight."
        )

        assert result["electricity_kwh"] == 2500.0   # 2.5 MWh * 1000
        assert result["gasoline_gallons"] == 100.0
        assert result["revenue_usd"] == 5_200_000.0
        assert result["waste_metric_tons"] == 15.0
        assert result["employee_count"] == 250.0
        assert result["freight_ton_miles"] == 1000.0
