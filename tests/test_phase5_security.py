"""Phase 5 tests — Security & Authorization Hardening."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, AsyncMock

from tests.conftest import TestSessionLocal

REGISTER_PAYLOAD = {
    "email": "phase5@example.com",
    "password": "Securepass123!",
    "full_name": "Phase5 User",
    "company_name": "Phase5Corp",
    "industry": "technology",
    "region": "US",
}

MEMBER_PAYLOAD = {
    "email": "member5@example.com",
    "password": "Securepass123!",
    "full_name": "Member User",
    "company_name": "MemberCorp",
    "industry": "energy",
    "region": "EU",
}


async def _register_and_login(client: AsyncClient, payload: dict | None = None) -> str:
    """Register a user and return an access token."""
    p = payload or REGISTER_PAYLOAD
    await client.post("/api/v1/auth/register", json=p)
    resp = await client.post("/api/v1/auth/login", json={
        "email": p["email"],
        "password": p["password"],
    })
    return resp.json()["access_token"]


async def _make_member(email: str) -> None:
    """Demote a registered user to 'member' role."""
    from api.models import User
    async with TestSessionLocal() as session:
        await session.execute(
            update(User).where(User.email == email).values(role="member")
        )
        await session.commit()


# ── S1: authenticate_user rejects inactive/deleted users ────────────


@pytest.mark.asyncio
class TestAuthenticateUserSecurity:
    async def test_login_rejected_for_inactive_user(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
        # Deactivate
        from api.models import User
        async with TestSessionLocal() as session:
            await session.execute(
                update(User).where(User.email == REGISTER_PAYLOAD["email"]).values(is_active=False)
            )
            await session.commit()

        resp = await client.post("/api/v1/auth/login", json={
            "email": REGISTER_PAYLOAD["email"],
            "password": REGISTER_PAYLOAD["password"],
        })
        assert resp.status_code == 401

    async def test_login_rejected_for_soft_deleted_user(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
        from api.models import User, _utcnow
        async with TestSessionLocal() as session:
            await session.execute(
                update(User).where(User.email == REGISTER_PAYLOAD["email"]).values(deleted_at=_utcnow())
            )
            await session.commit()

        resp = await client.post("/api/v1/auth/login", json={
            "email": REGISTER_PAYLOAD["email"],
            "password": REGISTER_PAYLOAD["password"],
        })
        assert resp.status_code == 401


# ── S2: Password reset tokens persisted in DB ──────────────────────


@pytest.mark.asyncio
class TestPasswordResetTokenDB:
    @patch("api.services.email.send_password_reset_email", new_callable=AsyncMock)
    async def test_db_backed_reset_flow(self, mock_email, client: AsyncClient):
        await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

        from api.auth import create_reset_token
        from api.models import User, PasswordResetToken

        async with TestSessionLocal() as session:
            result = await session.execute(select(User).where(User.email == REGISTER_PAYLOAD["email"]))
            user = result.scalar_one()
            token = await create_reset_token(session, user.id, user.email)
            await session.commit()

            # Verify token row exists
            rows = await session.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
            assert rows.scalar_one_or_none() is not None

        # Reset works
        resp = await client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": "NewSecure456!",
        })
        assert resp.status_code == 204

        # Token consumed — can't reuse
        resp = await client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": "AnotherPass789!",
        })
        assert resp.status_code == 400


# ── S3: Refresh endpoint rate-limited ───────────────────────────────


@pytest.mark.asyncio
class TestRefreshRateLimit:
    async def test_refresh_endpoint_exists_with_rate_limit(self, client: AsyncClient):
        """Refresh endpoint should accept request param and be decorated with limiter.
        We just verify the endpoint exists and rejects unauthenticated requests."""
        resp = await client.post("/api/v1/auth/refresh", json={})
        # No valid refresh token in body or cookie → 401
        assert resp.status_code == 401


# ── A1-A5: Admin-only route enforcement ────────────────────────


@pytest.mark.asyncio
class TestAdminOnlyRoutes:
    async def test_company_update_requires_admin(self, client: AsyncClient):
        token = await _register_and_login(client)
        await _make_member(REGISTER_PAYLOAD["email"])
        resp = await client.patch(
            "/api/v1/company",
            json={"name": "NewName"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "Admin" in resp.json()["detail"]

    async def test_subscription_change_requires_admin(self, client: AsyncClient):
        token = await _register_and_login(client)
        await _make_member(REGISTER_PAYLOAD["email"])
        resp = await client.post(
            "/api/v1/billing/subscription",
            json={"plan": "pro"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_credit_grant_requires_admin(self, client: AsyncClient):
        token = await _register_and_login(client)
        await _make_member(REGISTER_PAYLOAD["email"])
        resp = await client.post(
            "/api/v1/billing/credits/grant?amount=100",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_audit_logs_require_admin(self, client: AsyncClient):
        token = await _register_and_login(client)
        await _make_member(REGISTER_PAYLOAD["email"])
        resp = await client.get(
            "/api/v1/audit-logs/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_webhook_create_requires_admin(self, client: AsyncClient):
        token = await _register_and_login(client)
        await _make_member(REGISTER_PAYLOAD["email"])
        resp = await client.post(
            "/api/v1/webhooks/",
            json={"url": "https://example.com/hook", "event_types": ["report.created"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_supply_chain_verify_requires_admin(self, client: AsyncClient):
        token = await _register_and_login(client)
        await _make_member(REGISTER_PAYLOAD["email"])
        resp = await client.patch(
            "/api/v1/supply-chain/links/fake-id",
            json={"status": "verified"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_alert_check_requires_admin(self, client: AsyncClient):
        token = await _register_and_login(client)
        await _make_member(REGISTER_PAYLOAD["email"])
        resp = await client.post(
            "/api/v1/alerts/check",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_admin_can_trigger_alert_check(self, client: AsyncClient):
        token = await _register_and_login(client, payload={
            "email": "admin-alerts@example.com",
            "password": "Securepass123!",
            "full_name": "Admin Alerts",
            "company_name": "AdminAlertCorp",
            "industry": "technology",
            "region": "US",
        })
        resp = await client.post(
            "/api/v1/alerts/check",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_admin_can_update_company(self, client: AsyncClient):
        """Admin users should be able to update company — positive test."""
        token = await _register_and_login(client)  # admin by default
        resp = await client.patch(
            "/api/v1/company",
            json={"name": "Updated Corp"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Corp"

    async def test_review_approve_requires_admin(self, client: AsyncClient):
        token = await _register_and_login(client)
        await _make_member(REGISTER_PAYLOAD["email"])
        headers = {"Authorization": f"Bearer {token}"}

        upload = await client.post(
            "/api/v1/data",
            json={"year": 2024, "provided_data": {"electricity_kwh": 100000}},
            headers=headers,
        )
        assert upload.status_code == 201
        report = await client.post(
            "/api/v1/estimate",
            json={"data_upload_id": upload.json()["id"]},
            headers=headers,
        )
        assert report.status_code == 201

        review = await client.post(
            "/api/v1/reviews",
            json={"report_id": report.json()["id"]},
            headers=headers,
        )
        assert review.status_code == 201

        submit = await client.post(
            f"/api/v1/reviews/{review.json()['id']}/action",
            json={"action": "submit"},
            headers=headers,
        )
        assert submit.status_code == 200

        approve = await client.post(
            f"/api/v1/reviews/{review.json()['id']}/action",
            json={"action": "approve", "notes": "looks good"},
            headers=headers,
        )
        assert approve.status_code == 403

    async def test_review_reject_requires_admin(self, client: AsyncClient):
        token = await _register_and_login(client)
        await _make_member(REGISTER_PAYLOAD["email"])
        headers = {"Authorization": f"Bearer {token}"}

        upload = await client.post(
            "/api/v1/data",
            json={"year": 2024, "provided_data": {"electricity_kwh": 100000}},
            headers=headers,
        )
        assert upload.status_code == 201
        report = await client.post(
            "/api/v1/estimate",
            json={"data_upload_id": upload.json()["id"]},
            headers=headers,
        )
        assert report.status_code == 201

        review = await client.post(
            "/api/v1/reviews",
            json={"report_id": report.json()["id"]},
            headers=headers,
        )
        assert review.status_code == 201

        submit = await client.post(
            f"/api/v1/reviews/{review.json()['id']}/action",
            json={"action": "submit"},
            headers=headers,
        )
        assert submit.status_code == 200

        reject = await client.post(
            f"/api/v1/reviews/{review.json()['id']}/action",
            json={"action": "reject", "notes": "needs revision"},
            headers=headers,
        )
        assert reject.status_code == 403


# ── D1-D2: deleted_at filters on AI & compliance routes ─────────


@pytest.mark.asyncio
class TestDeletedAtFilters:
    @staticmethod
    async def _create_report(auth_client: AsyncClient) -> str:
        """Create a data upload + estimate and return the report ID."""
        upload = await auth_client.post("/api/v1/data", json={
            "year": 2023,
            "provided_data": {"electricity_kwh": 100000},
        })
        upload_id = upload.json()["id"]
        est = await auth_client.post("/api/v1/estimate", json={"data_upload_id": upload_id})
        assert est.status_code == 201, f"Estimate failed: {est.status_code} {est.text}"
        report_id = est.json()["id"]
        return report_id

    async def test_ai_audit_trail_excludes_deleted_report(self, auth_client: AsyncClient):
        """Soft-deleted reports should not be accessible via /ai/audit-trail."""
        report_id = await self._create_report(auth_client)

        # Soft-delete the report
        await auth_client.delete(f"/api/v1/reports/{report_id}")

        # AI audit trail should 404
        resp = await auth_client.post("/api/v1/ai/audit-trail", json={"report_id": report_id})
        assert resp.status_code == 404

    async def test_ai_recommendations_excludes_deleted_report(self, auth_client: AsyncClient):
        report_id = await self._create_report(auth_client)

        await auth_client.delete(f"/api/v1/reports/{report_id}")
        resp = await auth_client.get(f"/api/v1/ai/recommendations/{report_id}")
        assert resp.status_code == 404

    async def test_compliance_excludes_deleted_report(self, auth_client: AsyncClient):
        report_id = await self._create_report(auth_client)

        await auth_client.delete(f"/api/v1/reports/{report_id}")
        resp = await auth_client.post("/api/v1/compliance/report", json={
            "report_id": report_id,
            "framework": "ghg_protocol",
        })
        assert resp.status_code == 404


# ── D3: Soft delete supply chain links ──────────────────────────


@pytest.mark.asyncio
class TestSupplyChainSoftDelete:
    async def test_delete_link_is_soft(self, auth_client: AsyncClient):
        """Deleting a supply chain link should soft-delete, not hard-delete."""
        # We need a second company to link to
        from api.models import Company, SupplyChainLink
        async with TestSessionLocal() as session:
            from api.models import _new_id
            supplier = Company(id=_new_id(), name="SupplierCo", industry="energy", region="US")
            session.add(supplier)
            await session.commit()
            supplier_id = supplier.id

        # Create link
        resp = await auth_client.post("/api/v1/supply-chain/links", json={
            "supplier_company_id": supplier_id,
            "spend_usd": 50000,
            "category": "purchased_goods",
        })
        assert resp.status_code == 201
        link_id = resp.json()["id"]

        # Delete
        resp = await auth_client.delete(f"/api/v1/supply-chain/links/{link_id}")
        assert resp.status_code == 204

        # Should be soft-deleted — row still exists in DB with deleted_at set
        async with TestSessionLocal() as session:
            result = await session.execute(select(SupplyChainLink).where(SupplyChainLink.id == link_id))
            link = result.scalar_one()
            assert link.deleted_at is not None

        # Should not appear in supplier list
        resp = await auth_client.get("/api/v1/supply-chain/suppliers")
        assert resp.status_code == 200
        ids = [s["link_id"] for s in resp.json()["items"]]
        assert link_id not in ids


# ── S4: X-Forwarded-For rate limiter ────────────────────────────


@pytest.mark.asyncio
class TestRateLimiterProxy:
    def test_limiter_uses_custom_key_func(self):
        """The limiter should use our custom _get_real_ip, not get_remote_address."""
        from api.limiter import _get_real_ip, limiter
        # Verify our custom function is importable and the limiter key_func is set
        assert callable(_get_real_ip)
        # limiter._key_func should be our custom function
        assert limiter._key_func is _get_real_ip
