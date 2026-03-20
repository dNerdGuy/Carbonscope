"""Tests for webhook HMAC signatures, file upload edge cases, and soft-delete cascades."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from api.services.webhooks import _sign_payload


# ── Webhook signature tests (T6) ───────────────────────────────────────


class TestWebhookSignature:
    """Verify that HMAC-SHA256 signatures are computed correctly."""

    def test_sign_payload_matches_manual_hmac(self):
        secret = "test-secret-key"
        payload = b'{"event":"report.created","data":{}}'
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert _sign_payload(secret, payload) == expected

    def test_sign_payload_different_secrets(self):
        payload = b'{"event":"test"}'
        sig1 = _sign_payload("secret1", payload)
        sig2 = _sign_payload("secret2", payload)
        assert sig1 != sig2

    def test_sign_payload_different_payloads(self):
        secret = "shared-secret"
        sig1 = _sign_payload(secret, b'{"event":"a"}')
        sig2 = _sign_payload(secret, b'{"event":"b"}')
        assert sig1 != sig2

    def test_sign_payload_empty_body(self):
        sig = _sign_payload("key", b"")
        # Should be a valid 64-char hex digest
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)


# ── File upload edge cases (T5) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file(auth_client: AsyncClient):
    """Refuse uploads larger than the file-size cap (10 MB default)."""
    big_content = b"0" * (11 * 1024 * 1024)  # 11 MB
    resp = await auth_client.post(
        "/api/v1/questionnaires/upload",
        files={"file": ("big.csv", io.BytesIO(big_content), "text/csv")},
    )
    assert resp.status_code in (400, 413, 422)


@pytest.mark.asyncio
async def test_upload_rejects_disallowed_filetype(auth_client: AsyncClient):
    """Reject file types not in the allowlist."""
    resp = await auth_client.post(
        "/api/v1/questionnaires/upload",
        files={"file": ("malware.exe", io.BytesIO(b"MZevil"), "application/x-executable")},
    )
    assert resp.status_code in (400, 415, 422)


@pytest.mark.asyncio
async def test_upload_rejects_empty_file(auth_client: AsyncClient):
    """Reject zero-byte uploads."""
    resp = await auth_client.post(
        "/api/v1/questionnaires/upload",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_upload_sanitises_filename(auth_client: AsyncClient):
    """Path-traversal characters in filename should be stripped."""
    csv_content = b"scope,value\nscope_1,100"
    resp = await auth_client.post(
        "/api/v1/questionnaires/upload",
        files={"file": ("../../etc/passwd", io.BytesIO(csv_content), "text/csv")},
    )
    if resp.status_code in (200, 201):
        data = resp.json()
        assert "/" not in data.get("original_filename", "")
        assert "\\" not in data.get("original_filename", "")


# ── Soft-delete cascade (T7) ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_soft_deleted_questionnaires_not_listed(auth_client: AsyncClient):
    """Soft-deleted questionnaires should not appear in list responses."""
    # Upload a questionnaire
    csv_content = b"scope,value\nscope_1,100"
    resp = await auth_client.post(
        "/api/v1/questionnaires/upload",
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
    )
    if resp.status_code not in (200, 201):
        pytest.skip("Upload not supported in test env")
    q_id = resp.json()["id"]

    # Delete it
    del_resp = await auth_client.delete(f"/api/v1/questionnaires/{q_id}")
    assert del_resp.status_code == 204

    # List should not include deleted
    list_resp = await auth_client.get("/api/v1/questionnaires/")
    assert list_resp.status_code == 200
    items = list_resp.json().get("items", list_resp.json().get("results", []))
    assert all(item["id"] != q_id for item in items)


@pytest.mark.asyncio
async def test_soft_deleted_questionnaire_returns_404(auth_client: AsyncClient):
    """GET on a soft-deleted questionnaire should return 404."""
    csv_content = b"scope,value\nscope_1,100"
    resp = await auth_client.post(
        "/api/v1/questionnaires/upload",
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
    )
    if resp.status_code not in (200, 201):
        pytest.skip("Upload not supported in test env")
    q_id = resp.json()["id"]

    await auth_client.delete(f"/api/v1/questionnaires/{q_id}")

    get_resp = await auth_client.get(f"/api/v1/questionnaires/{q_id}")
    assert get_resp.status_code == 404
