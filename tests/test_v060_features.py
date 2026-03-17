"""Tests for v0.6.0 features — refresh tokens, password reset, SSRF validation,
middleware, admin dep, marketplace seller management, plan downgrade."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


# ── SSRF Validation ──────────────────────────────────────────────────


class TestURLValidator:
    def test_blocks_localhost(self):
        from api.services.url_validator import validate_webhook_url

        with pytest.raises(ValueError, match="not allowed"):
            validate_webhook_url("http://localhost/hook")

    def test_blocks_zero_addr(self):
        from api.services.url_validator import validate_webhook_url

        with pytest.raises(ValueError, match="not allowed"):
            validate_webhook_url("http://0.0.0.0/hook")

    def test_blocks_metadata_gcp(self):
        from api.services.url_validator import validate_webhook_url

        with pytest.raises(ValueError, match="not allowed"):
            validate_webhook_url("http://metadata.google.internal/computeMetadata/v1/")

    def test_blocks_metadata_aws(self):
        from api.services.url_validator import validate_webhook_url

        with pytest.raises(ValueError, match="not allowed"):
            validate_webhook_url("http://169.254.169.254/latest/meta-data/")

    def test_blocks_non_http_scheme(self):
        from api.services.url_validator import validate_webhook_url

        with pytest.raises(ValueError, match="http or https"):
            validate_webhook_url("ftp://example.com/hook")

    def test_blocks_no_hostname(self):
        from api.services.url_validator import validate_webhook_url

        with pytest.raises(ValueError, match="valid hostname"):
            validate_webhook_url("http:///hook")

    @patch("api.services.url_validator.socket.getaddrinfo")
    def test_blocks_private_ip_resolution(self, mock_getaddr):
        from api.services.url_validator import validate_webhook_url
        import socket

        # Simulate resolving to a private IP
        mock_getaddr.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.0.0.1", 443))
        ]
        with pytest.raises(ValueError, match="private/reserved"):
            validate_webhook_url("https://evil.example.com/hook")

    @patch("api.services.url_validator.socket.getaddrinfo")
    def test_allows_public_ip(self, mock_getaddr):
        from api.services.url_validator import validate_webhook_url
        import socket

        mock_getaddr.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("203.0.113.1", 443))
        ]
        # Should not raise
        validate_webhook_url("https://public.example.com/hook")


# ── Refresh Token Routes ─────────────────────────────────────────────


@pytest.mark.asyncio
class TestRefreshTokenFlow:
    async def test_login_returns_refresh_token(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "refresh@example.com",
            "password": "Password123!",
            "full_name": "Refresh User",
            "company_name": "RefreshCorp",
            "industry": "energy",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "refresh@example.com",
            "password": "Password123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_token_rotation(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "rotate@example.com",
            "password": "Password123!",
            "full_name": "Rotate User",
            "company_name": "RotateCorp",
            "industry": "retail",
        })
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "rotate@example.com",
            "password": "Password123!",
        })
        refresh_token = login_resp.json()["refresh_token"]

        # Use refresh token to get new tokens
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # New refresh token should be different (rotation)
        assert data["refresh_token"] != refresh_token

    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid-token-garbage",
        })
        assert resp.status_code == 401

    async def test_old_refresh_token_invalidated(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "oldr@example.com",
            "password": "Password123!",
            "full_name": "Old Refresh",
            "company_name": "OldCorp",
            "industry": "technology",
        })
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "oldr@example.com",
            "password": "Password123!",
        })
        old_refresh = login_resp.json()["refresh_token"]

        # Rotate
        await client.post("/api/v1/auth/refresh", json={
            "refresh_token": old_refresh,
        })

        # Old token should now be invalid
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": old_refresh,
        })
        assert resp.status_code == 401


# ── Password Reset Flow ──────────────────────────────────────────────


@pytest.mark.asyncio
class TestPasswordReset:
    @patch("api.services.email.send_password_reset_email", new_callable=AsyncMock)
    async def test_forgot_password_existing_email(self, mock_email, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "forgot@example.com",
            "password": "Password123!",
            "full_name": "Forgot User",
            "company_name": "ForgotCorp",
            "industry": "manufacturing",
        })
        resp = await client.post("/api/v1/auth/forgot-password", json={
            "email": "forgot@example.com",
        })
        # Always 204 regardless of email existence
        assert resp.status_code == 204
        mock_email.assert_awaited_once()

    async def test_forgot_password_nonexistent_no_leak(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/forgot-password", json={
            "email": "nonexistent@example.com",
        })
        # Should still return 204 to prevent email enumeration
        assert resp.status_code == 204

    @patch("api.services.email.send_password_reset_email", new_callable=AsyncMock)
    async def test_reset_password_full_flow(self, mock_email, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "reset@example.com",
            "password": "OldPassword123!",
            "full_name": "Reset User",
            "company_name": "ResetCorp",
            "industry": "energy",
        })
        # Trigger forgot-password to get a token
        from api.auth import create_reset_token
        from api.models import User
        from sqlalchemy import select
        from tests.conftest import TestSessionLocal

        async with TestSessionLocal() as session:
            result = await session.execute(select(User).where(User.email == "reset@example.com"))
            user = result.scalar_one()
            token = await create_reset_token(session, user.id, user.email)
            await session.commit()

        # Reset password
        resp = await client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": "NewPassword456!",
        })
        assert resp.status_code == 204

        # Login with new password
        resp = await client.post("/api/v1/auth/login", json={
            "email": "reset@example.com",
            "password": "NewPassword456!",
        })
        assert resp.status_code == 200

        # Old password should fail
        resp = await client.post("/api/v1/auth/login", json={
            "email": "reset@example.com",
            "password": "OldPassword123!",
        })
        assert resp.status_code == 401

    async def test_reset_password_invalid_token(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/reset-password", json={
            "token": "bogus-token",
            "new_password": "NewPassword456!",
        })
        assert resp.status_code == 400


# ── Middleware ────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestMiddleware:
    async def test_response_has_request_id(self, client: AsyncClient):
        resp = await client.get("/api/v1/health")
        assert "x-request-id" in resp.headers

    async def test_custom_request_id_echoed(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/health",
            headers={"X-Request-ID": "my-custom-id-123"},
        )
        assert resp.headers.get("x-request-id") == "my-custom-id-123"

    async def test_security_headers(self, client: AsyncClient):
        resp = await client.get("/api/v1/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("x-xss-protection") == "1; mode=block"
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "camera=()" in resp.headers.get("permissions-policy", "")


# ── Admin Dependency ─────────────────────────────────────────────────


@pytest.mark.asyncio
class TestAdminAccess:
    async def test_admin_user_has_access(self, auth_client: AsyncClient):
        # auth_client registers as admin by default
        resp = await auth_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"


# ── Marketplace Seller Management ────────────────────────────────────


@pytest.mark.asyncio
class TestMarketplaceSeller:
    async def _setup_listing(self, auth_client: AsyncClient) -> str:
        """Create a data upload, report, and listing. Return the listing ID."""
        # Upgrade to pro plan (marketplace requires it)
        await auth_client.post("/api/v1/billing/subscription", json={"plan": "pro"})

        # Upload data
        up_resp = await auth_client.post("/api/v1/data", json={
            "year": 2023,
            "provided_data": {"electricity_kwh": 50000},
            "notes": "Test data",
        })
        upload_id = up_resp.json()["id"]

        # Create a report via estimation
        est_resp = await auth_client.post("/api/v1/estimate", json={
            "data_upload_id": upload_id,
        })
        report_id = est_resp.json()["id"]

        # Create a marketplace listing
        listing_resp = await auth_client.post("/api/v1/marketplace/listings", json={
            "title": "Test Dataset",
            "description": "A test listing",
            "data_type": "benchmark",
            "report_id": report_id,
            "price_credits": 10,
        })
        assert listing_resp.status_code == 201
        return listing_resp.json()["id"]

    async def test_list_my_listings(self, auth_client: AsyncClient):
        listing_id = await self._setup_listing(auth_client)
        resp = await auth_client.get("/api/v1/marketplace/my-listings")
        assert resp.status_code == 200
        data = resp.json()
        assert any(item["id"] == listing_id for item in data["items"])

    async def test_withdraw_listing(self, auth_client: AsyncClient):
        listing_id = await self._setup_listing(auth_client)
        resp = await auth_client.post(f"/api/v1/marketplace/listings/{listing_id}/withdraw")
        assert resp.status_code == 200
        assert resp.json()["status"] == "withdrawn"


# ── Plan Change & Downgrade ──────────────────────────────────────────


@pytest.mark.asyncio
class TestPlanChange:
    async def test_upgrade_plan(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/billing/subscription", json={"plan": "pro"})
        assert resp.status_code == 200
        assert resp.json()["plan"] == "pro"

    async def test_downgrade_plan(self, auth_client: AsyncClient):
        # Upgrade then downgrade
        await auth_client.post("/api/v1/billing/subscription", json={"plan": "pro"})
        resp = await auth_client.post("/api/v1/billing/subscription", json={"plan": "free"})
        assert resp.status_code == 200
        assert resp.json()["plan"] == "free"

    async def test_credits_after_plan(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/billing/credits")
        assert resp.status_code == 200
        data = resp.json()
        assert "balance" in data
        assert isinstance(data["balance"], (int, float))


# ── Supply Chain Routes ──────────────────────────────────────────────


@pytest.mark.asyncio
class TestSupplyChainRoutes:
    async def _register_second_company(self, client: AsyncClient) -> str:
        """Register a second company and return its company_id."""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "supplier@example.com",
            "password": "Password123!",
            "full_name": "Supplier User",
            "company_name": "SupplierCorp",
            "industry": "manufacturing",
            "region": "CN",
        })
        return resp.json()["company_id"]

    async def test_add_supplier(self, client: AsyncClient, auth_client: AsyncClient):
        supplier_company_id = await self._register_second_company(client)
        resp = await auth_client.post("/api/v1/supply-chain/links", json={
            "supplier_company_id": supplier_company_id,
            "spend_usd": 50000,
            "category": "raw_materials",
        })
        assert resp.status_code == 201
        assert resp.json()["supplier_company_id"] == supplier_company_id

    async def test_list_suppliers(self, client: AsyncClient, auth_client: AsyncClient):
        supplier_company_id = await self._register_second_company(client)
        await auth_client.post("/api/v1/supply-chain/links", json={
            "supplier_company_id": supplier_company_id,
            "spend_usd": 50000,
            "category": "raw_materials",
        })
        resp = await auth_client.get("/api/v1/supply-chain/suppliers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_scope3_from_suppliers(self, client: AsyncClient, auth_client: AsyncClient):
        supplier_company_id = await self._register_second_company(client)
        await auth_client.post("/api/v1/supply-chain/links", json={
            "supplier_company_id": supplier_company_id,
            "spend_usd": 50000,
            "category": "raw_materials",
        })
        resp = await auth_client.get("/api/v1/supply-chain/scope3-from-suppliers")
        assert resp.status_code == 200
        data = resp.json()
        assert "supplier_count" in data

    async def test_delete_supply_chain_link(self, client: AsyncClient, auth_client: AsyncClient):
        supplier_company_id = await self._register_second_company(client)
        create_resp = await auth_client.post("/api/v1/supply-chain/links", json={
            "supplier_company_id": supplier_company_id,
        })
        link_id = create_resp.json()["id"]
        del_resp = await auth_client.delete(f"/api/v1/supply-chain/links/{link_id}")
        assert del_resp.status_code == 204


# ── Audit Log Route ──────────────────────────────────────────────────


@pytest.mark.asyncio
class TestAuditLog:
    async def test_audit_logs_accessible(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/audit-logs/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_audit_log_after_password_change(self, auth_client: AsyncClient):
        # Change password generates an audit entry
        await auth_client.post("/api/v1/auth/change-password", json={
            "current_password": "Securepass123!",
            "new_password": "NewSecure456!",
        })
        resp = await auth_client.get("/api/v1/audit-logs/")
        data = resp.json()
        actions = [entry["action"] for entry in data["items"]]
        assert "change_password" in actions
