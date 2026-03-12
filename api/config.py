"""Application configuration — loaded from environment variables."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Paths ───────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Environment ─────────────────────────────────────────────────────

ENV: str = os.getenv("ENV", "development")  # development | production | test

# ── Database ────────────────────────────────────────────────────────
# Supports SQLite (aiosqlite) and PostgreSQL (asyncpg).
# Examples:
#   sqlite+aiosqlite:///./carbonscope.db
#   postgresql+asyncpg://user:pass@localhost:5432/carbonscope

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{BASE_DIR / 'carbonscope.db'}",
)

if ENV == "production" and "sqlite" in DATABASE_URL:
    raise RuntimeError(
        "SQLite is not supported in production. Set DATABASE_URL to a PostgreSQL connection string. "
        "Example: postgresql+asyncpg://user:pass@localhost:5432/carbonscope"
    )

# ── Auth ────────────────────────────────────────────────────────────

_DEFAULT_SECRET = "change-me-in-production"
SECRET_KEY: str = os.getenv("SECRET_KEY", _DEFAULT_SECRET)
if SECRET_KEY == _DEFAULT_SECRET:
    if ENV == "production":
        raise RuntimeError(
            "SECRET_KEY must be set to a secure random value in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    logger.warning(
        "SECRET_KEY is using the default value. Set SECRET_KEY env var in production!"
    )

# Validate SECRET_KEY quality
if ENV == "production":
    if len(SECRET_KEY) < 32:
        raise RuntimeError("SECRET_KEY must be at least 32 characters in production.")
    if len(set(SECRET_KEY)) < 10:
        raise RuntimeError("SECRET_KEY appears to lack sufficient randomness.")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ── CORS ────────────────────────────────────────────────────────────

ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]

# ── Rate Limiting ───────────────────────────────────────────────────

RATE_LIMIT_AUTH: str = os.getenv("RATE_LIMIT_AUTH", "10/minute")
RATE_LIMIT_DEFAULT: str = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")

# ── Cookies / CSRF ──────────────────────────────────────────────────

COOKIE_SECURE: bool = ENV == "production"
COOKIE_SAMESITE: str = "lax"
COOKIE_DOMAIN: str | None = os.getenv("COOKIE_DOMAIN", None)

# ── Logging ─────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# ── Bittensor ───────────────────────────────────────────────────────

BT_NETWORK: str = os.getenv("BT_NETWORK", "test")
BT_NETUID: int = int(os.getenv("BT_NETUID", "1"))
BT_WALLET_NAME: str = os.getenv("BT_WALLET_NAME", "api_client")
BT_WALLET_HOTKEY: str = os.getenv("BT_WALLET_HOTKEY", "default")
BT_QUERY_TIMEOUT: float = float(os.getenv("BT_QUERY_TIMEOUT", "30.0"))
ESTIMATION_MODE: str = os.getenv("ESTIMATION_MODE", "local")  # local | subnet

# ── Email / SMTP ────────────────────────────────────────────────────
# Configured in api/services/email.py via env vars:
#   SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM
