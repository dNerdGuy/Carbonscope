"""Webhook and continuous monitoring service.

Manages webhook subscriptions and dispatches notifications when
emission-related events occur (report created, data uploaded, etc.).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Webhook

logger = logging.getLogger(__name__)

# Supported event types
EVENT_TYPES = [
    "report.created",
    "data.uploaded",
    "estimate.completed",
    "supply_chain.link_created",
    "supply_chain.link_verified",
    "confidence.improved",
]


async def create_webhook(
    db: AsyncSession,
    company_id: str,
    url: str,
    event_types: list[str],
) -> Webhook:
    """Register a new webhook endpoint for a company."""
    # Validate event types
    invalid = [e for e in event_types if e not in EVENT_TYPES]
    if invalid:
        raise ValueError(f"Invalid event types: {invalid}. Valid: {EVENT_TYPES}")

    secret = secrets.token_urlsafe(32)
    webhook = Webhook(
        company_id=company_id,
        url=url,
        event_types=event_types,
        secret=secret,
        active=1,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return webhook


async def list_webhooks(
    db: AsyncSession,
    company_id: str,
) -> list[Webhook]:
    """List all webhooks for a company."""
    result = await db.execute(
        select(Webhook).where(Webhook.company_id == company_id)
    )
    return list(result.scalars().all())


async def delete_webhook(
    db: AsyncSession,
    webhook_id: str,
    company_id: str,
) -> bool:
    """Delete a webhook (scoped to company)."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.company_id == company_id,
        )
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        return False
    await db.delete(webhook)
    await db.commit()
    return True


async def toggle_webhook(
    db: AsyncSession,
    webhook_id: str,
    company_id: str,
    active: bool,
) -> Webhook | None:
    """Enable or disable a webhook."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.company_id == company_id,
        )
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        return None
    webhook.active = 1 if active else 0
    await db.commit()
    await db.refresh(webhook)
    return webhook


def _sign_payload(secret: str, payload: bytes) -> str:
    """Create HMAC-SHA256 signature for the webhook payload."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def dispatch_event(
    db: AsyncSession,
    company_id: str,
    event_type: str,
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Dispatch an event to all matching active webhooks for a company.

    Returns a list of dispatch results (webhook_id, status, error).
    In production this would use an async HTTP client; here we log and
    return the intended payloads for testability.
    """
    webhooks = await list_webhooks(db, company_id)
    results = []

    for wh in webhooks:
        if not wh.active:
            continue
        if event_type not in (wh.event_types or []):
            continue

        payload = json.dumps({
            "event": event_type,
            "company_id": company_id,
            "data": data,
        }).encode()

        signature = _sign_payload(wh.secret, payload)

        # In production: httpx.AsyncClient.post(wh.url, content=payload, headers=...)
        # For now, log the dispatch
        logger.info(
            "Webhook dispatch: event=%s webhook=%s url=%s",
            event_type, wh.id, wh.url,
        )
        results.append({
            "webhook_id": wh.id,
            "url": wh.url,
            "event": event_type,
            "signature": signature,
            "status": "dispatched",
        })

    return results
