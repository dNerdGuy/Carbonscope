#!/usr/bin/env python3
"""Validate required environment variables and service connectivity at startup."""

import os
import sys


def main() -> None:
    errors: list[str] = []

    # --- Required env vars ---
    required = ["SECRET_KEY", "DATABASE_URL", "TOTP_ENCRYPTION_KEY"]
    for var in required:
        if not os.getenv(var):
            errors.append(f"Missing required env var: {var}")

    # --- Optional but warn ---
    warnings: list[str] = []
    optional = ["SMTP_HOST", "STRIPE_SECRET_KEY", "REDIS_URL", "SENTRY_DSN"]
    for var in optional:
        if not os.getenv(var):
            warnings.append(f"Optional env var not set: {var}")

    # --- Validate SECRET_KEY length ---
    secret = os.getenv("SECRET_KEY", "")
    if secret and len(secret) < 32:
        errors.append("SECRET_KEY should be at least 32 characters")

    # --- Validate DATABASE_URL scheme ---
    db_url = os.getenv("DATABASE_URL", "")
    if db_url and not (
        db_url.startswith("postgresql") or db_url.startswith("sqlite")
    ):
        errors.append(f"DATABASE_URL has unexpected scheme: {db_url.split('://')[0]}")

    # --- Check DB connectivity ---
    if db_url:
        try:
            if "sqlite" in db_url:
                import sqlite3
                conn = sqlite3.connect(db_url.replace("sqlite:///", "").replace("sqlite+aiosqlite:///", ""))
                conn.close()
            else:
                import socket
                # Parse host:port from DATABASE_URL
                from urllib.parse import urlparse
                parsed = urlparse(db_url.replace("+asyncpg", "").replace("+psycopg", ""))
                host = parsed.hostname or "localhost"
                port = parsed.port or 5432
                sock = socket.create_connection((host, port), timeout=5)
                sock.close()
        except Exception as e:
            errors.append(f"Cannot connect to database: {e}")

    # --- Check Redis connectivity ---
    redis_url = os.getenv("REDIS_URL", "")
    if redis_url:
        try:
            import socket
            from urllib.parse import urlparse
            parsed = urlparse(redis_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 6379
            sock = socket.create_connection((host, port), timeout=5)
            sock.close()
        except Exception as e:
            warnings.append(f"Cannot connect to Redis: {e}")

    # --- Report ---
    for w in warnings:
        print(f"  WARN: {w}", file=sys.stderr)

    if errors:
        print(f"\n{'='*50}", file=sys.stderr)
        print("STARTUP VALIDATION FAILED", file=sys.stderr)
        print(f"{'='*50}", file=sys.stderr)
        for err in errors:
            print(f"  ERROR: {err}", file=sys.stderr)
        sys.exit(1)
    else:
        print("Startup validation passed.")


if __name__ == "__main__":
    main()
