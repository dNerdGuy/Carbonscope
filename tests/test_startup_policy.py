"""Startup policy tests for production SMTP validation."""

from __future__ import annotations

import logging

import pytest

import api.main as main


def _clear_smtp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)


def test_validate_production_smtp_raises_when_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "ENV", "production")
    monkeypatch.setattr(main, "REQUIRE_SMTP_IN_PRODUCTION", True)
    _clear_smtp_env(monkeypatch)

    with pytest.raises(RuntimeError, match="SMTP not configured in production"):
        main._validate_production_smtp()


def test_validate_production_smtp_warns_when_not_required(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(main, "ENV", "production")
    monkeypatch.setattr(main, "REQUIRE_SMTP_IN_PRODUCTION", False)
    _clear_smtp_env(monkeypatch)

    with caplog.at_level(logging.WARNING):
        main._validate_production_smtp()

    assert "SMTP not configured in production" in caplog.text


def test_validate_production_smtp_passes_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "ENV", "production")
    monkeypatch.setattr(main, "REQUIRE_SMTP_IN_PRODUCTION", True)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "password")

    main._validate_production_smtp()


def test_validate_production_smtp_skips_non_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "ENV", "development")
    monkeypatch.setattr(main, "REQUIRE_SMTP_IN_PRODUCTION", True)
    _clear_smtp_env(monkeypatch)

    main._validate_production_smtp()
