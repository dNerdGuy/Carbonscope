"""Tests for Phase 3: logging, CSP, health check, request logging middleware."""

from __future__ import annotations

import logging

import pytest
from httpx import AsyncClient

from api.logging_config import _redact, SensitiveFilter, JSONFormatter, setup_logging
from api.main import APP_VERSION


# ── Sensitive data redaction ────────────────────────────────────────


class TestRedaction:
    def test_redact_password_json(self):
        msg = '{"Password": "hunter2", "email": "ok"}'
        assert "hunter2" not in _redact(msg)
        assert '***' in _redact(msg)

    def test_redact_token_kv(self):
        msg = "token=abc123secret something else"
        result = _redact(msg)
        assert "abc123secret" not in result
        assert "token=***" in result.lower() or "Token=***" in result

    def test_redact_email(self):
        msg = "User alice@example.com logged in"
        result = _redact(msg)
        assert "alice@example.com" not in result
        assert "[REDACTED_EMAIL]" in result

    def test_no_redaction_for_normal_text(self):
        msg = "Processing company report for year 2024"
        assert _redact(msg) == msg

    def test_redact_api_key_kv(self):
        msg = "api_key=sk-1234567890 was used"
        result = _redact(msg)
        assert "sk-1234567890" not in result


class TestSensitiveFilter:
    def test_filter_redacts_message(self):
        f = SensitiveFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Login for user@example.com with password=secret123",
            args=(), exc_info=None,
        )
        f.filter(record)
        assert "user@example.com" not in record.msg
        assert "secret123" not in record.msg

    def test_filter_returns_true(self):
        f = SensitiveFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="normal message", args=(), exc_info=None,
        )
        assert f.filter(record) is True


class TestJSONFormatter:
    def test_json_output(self):
        import json
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="api.test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        output = fmt.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["logger"] == "api.test"
        assert data["message"] == "hello world"
        assert "timestamp" in data


class TestSetupLogging:
    def test_setup_plain(self):
        setup_logging(level="DEBUG", json_output=False)
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) >= 1

    def test_setup_json(self):
        setup_logging(level="INFO", json_output=True)
        root = logging.getLogger()
        assert isinstance(root.handlers[0].formatter, JSONFormatter)
        # Reset to plain for other tests
        setup_logging(level="INFO", json_output=False)


# ── CSP Header ──────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestCSPHeader:
    async def test_csp_present(self, client: AsyncClient):
        resp = await client.get("/api/v1/health")
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp


# ── Expanded health check ──────────────────────────────────────────


@pytest.mark.asyncio
class TestHealthCheck:
    async def test_health_returns_ok(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"

    async def test_health_has_email_field(self, client: AsyncClient):
        resp = await client.get("/health")
        data = resp.json()
        assert "email" in data

    async def test_health_has_bittensor_field(self, client: AsyncClient):
        resp = await client.get("/health")
        data = resp.json()
        assert "bittensor" in data
        assert "local" in data["bittensor"] or "subnet" in data["bittensor"]

    async def test_health_has_version(self, client: AsyncClient):
        resp = await client.get("/health")
        data = resp.json()
        assert data["version"] == APP_VERSION

    async def test_health_has_db_pool_field(self, client: AsyncClient):
        resp = await client.get("/health")
        data = resp.json()
        assert "db_pool" in data
        assert isinstance(data["db_pool"], str)


# ── Metrics endpoint ───────────────────────────────────────────────


@pytest.mark.asyncio
class TestMetrics:
    async def test_metrics_public_access(self, client: AsyncClient):
        resp = await client.get("/metrics")
        assert resp.status_code == 200

    async def test_metrics_endpoint(self, auth_client: AsyncClient):
        resp = await auth_client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        assert "total_requests" in data
        assert data["total_requests"] >= 1
