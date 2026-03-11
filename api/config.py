"""Application configuration — loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Database ────────────────────────────────────────────────────────

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{BASE_DIR / 'carbonscope.db'}",
)

# ── Auth ────────────────────────────────────────────────────────────

SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ── Bittensor ───────────────────────────────────────────────────────

BT_NETWORK: str = os.getenv("BT_NETWORK", "test")
BT_NETUID: int = int(os.getenv("BT_NETUID", "1"))
BT_WALLET_NAME: str = os.getenv("BT_WALLET_NAME", "api_client")
BT_WALLET_HOTKEY: str = os.getenv("BT_WALLET_HOTKEY", "default")
BT_QUERY_TIMEOUT: float = float(os.getenv("BT_QUERY_TIMEOUT", "30.0"))
