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
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Webhook, WebhookDelivery

logger = logging.getLogger(__name__)

# Retry intervals in seconds for attempts 1, 2, 3
_RETRY_DELAYS = [1, 5, 30]

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
    # Validate URL against SSRF
    from api.services.url_validator import validate_webhook_url

    validate_webhook_url(url)

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
        active=True,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return webhook


async def list_webhooks(
    db: AsyncSession,
    company_id: str,
    limit: int | None = None,
    offset: int | None = None,
) -> tuple[list[Webhook], int]:
    """List webhooks for a company with optional DB-level pagination.

    Returns (items, total_count). If limit/offset are None, returns all.
    """
    from sqlalchemy import func

    base = select(Webhook).where(Webhook.company_id == company_id, Webhook.deleted_at.is_(None))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    query = base.order_by(Webhook.created_at.desc())
    if limit is not None:
        query = query.limit(limit)
    if offset is not None:
        query = query.offset(offset)

    result = await db.execute(query)
    return list(result.scalars().all()), total


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
            Webhook.deleted_at.is_(None),
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
            Webhook.deleted_at.is_(None),
        )
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        return None
    webhook.active = active
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

    Performs real HTTP POST requests and logs delivery results.
    Returns a list of dispatch results (webhook_id, status, error).
    """
    webhooks, _ = await list_webhooks(db, company_id)
    results = []

    for wh in webhooks:
        if not wh.active:
            continue
        if event_type not in (wh.event_types or []):
            continue

        payload_dict = {
            "event": event_type,
            "company_id": company_id,
            "data": data,
        }
        payload = json.dumps(payload_dict, default=str).encode()
        signature = _sign_payload(wh.secret, payload)

        headers = {
            "Content-Type": "application/json",
            "X-CarbonScope-Signature": f"sha256={signature}",
            "X-CarbonScope-Event": event_type,
        }

        delivery = WebhookDelivery(
            webhook_id=wh.id,
            event_type=event_type,
            payload=payload_dict,
        )

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(wh.url, content=payload, headers=headers)
            elapsed_ms = int((time.monotonic() - start) * 1000)

            delivery.status_code = resp.status_code
            delivery.response_body = resp.text[:2048]
            delivery.success = resp.status_code < 400
            delivery.duration_ms = elapsed_ms

            if not delivery.success and delivery.retry_count < delivery.max_retries:
                delay = _RETRY_DELAYS[min(delivery.retry_count, len(_RETRY_DELAYS) - 1)]
                delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

            results.append({
                "webhook_id": wh.id,
                "url": wh.url,
                "event": event_type,
                "status": "success" if delivery.success else "failed",
                "status_code": resp.status_code,
            })
        except (httpx.RequestError, httpx.TimeoutException, OSError) as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            delivery.success = False
            delivery.error = str(exc)[:2048]
            delivery.duration_ms = elapsed_ms

            if delivery.retry_count < delivery.max_retries:
                delay = _RETRY_DELAYS[min(delivery.retry_count, len(_RETRY_DELAYS) - 1)]
                delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

            logger.warning(
                "Webhook delivery failed: webhook=%s url=%s error=%s",
                wh.id, wh.url, exc,
            )
            results.append({
                "webhook_id": wh.id,
                "url": wh.url,
                "event": event_type,
                "status": "error",
                "error": str(exc),
            })

        db.add(delivery)

    await db.commit()
    return results


async def list_deliveries(
    db: AsyncSession,
    webhook_id: str,
    company_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[WebhookDelivery], int]:
    """List delivery logs for a webhook (scoped to company)."""
    from sqlalchemy import func

    # Verify webhook belongs to the company
    wh_result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.company_id == company_id,
            Webhook.deleted_at.is_(None),
        )
    )
    if wh_result.scalar_one_or_none() is None:
        return [], 0

    base = select(WebhookDelivery).where(WebhookDelivery.webhook_id == webhook_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    result = await db.execute(
        base.order_by(WebhookDelivery.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def dispatch_event_background(
    company_id: str,
    event_type: str,
    data: dict[str, Any],
) -> None:
    """Dispatch webhook event in the background (for use with BackgroundTasks).

    Opens its own DB session so it doesn't depend on the request lifecycle.
    """
    from api.database import async_session

    async with async_session() as db:
        await dispatch_event(db, company_id, event_type, data)


async def process_pending_retries(db: AsyncSession) -> int:
    """Process webhook deliveries that are due for retry.

    Returns the number of retries processed.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(WebhookDelivery).where(
            WebhookDelivery.success.is_(False),
            WebhookDelivery.next_retry_at.isnot(None),
            WebhookDelivery.next_retry_at <= now,
        ).limit(50)
    )
    pending = list(result.scalars().all())
    processed = 0

    for delivery in pending:
        # Look up the webhook to get URL and secret
        wh_result = await db.execute(
            select(Webhook).where(Webhook.id == delivery.webhook_id, Webhook.deleted_at.is_(None))
        )
        wh = wh_result.scalar_one_or_none()
        if not wh or not wh.active:
            delivery.next_retry_at = None  # stop retrying
            continue

        payload = json.dumps(delivery.payload, default=str).encode()
        signature = _sign_payload(wh.secret, payload)
        headers = {
            "Content-Type": "application/json",
            "X-CarbonScope-Signature": f"sha256={signature}",
            "X-CarbonScope-Event": delivery.event_type,
        }

        delivery.retry_count += 1
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(wh.url, content=payload, headers=headers)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            delivery.status_code = resp.status_code
            delivery.response_body = resp.text[:2048]
            delivery.success = resp.status_code < 400
            delivery.duration_ms = elapsed_ms
            delivery.error = None
        except (httpx.RequestError, httpx.TimeoutException, OSError) as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            delivery.duration_ms = elapsed_ms
            delivery.error = str(exc)[:2048]

        if delivery.success:
            delivery.next_retry_at = None
        elif delivery.retry_count >= delivery.max_retries:
            delivery.next_retry_at = None  # exhausted retries
            logger.warning(
                "Webhook delivery exhausted retries: delivery=%s webhook=%s",
                delivery.id, delivery.webhook_id,
            )
        else:
            delay = _RETRY_DELAYS[min(delivery.retry_count, len(_RETRY_DELAYS) - 1)]
            delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

        processed += 1

    await db.commit()
    return processed


async def retry_delivery(
    db: AsyncSession,
    delivery_id: str,
    company_id: str,
) -> WebhookDelivery | None:
    """Manually retry a specific failed delivery (admin action).

    Returns the updated delivery or None if not found / not owned.
    """
    result = await db.execute(
        select(WebhookDelivery)
        .join(Webhook, WebhookDelivery.webhook_id == Webhook.id)
        .where(
            WebhookDelivery.id == delivery_id,
            Webhook.company_id == company_id,
            Webhook.deleted_at.is_(None),
        )
    )
    delivery = result.scalar_one_or_none()
    if not delivery:
        return None

    wh_result = await db.execute(
        select(Webhook).where(Webhook.id == delivery.webhook_id)
    )
    wh = wh_result.scalar_one_or_none()
    if not wh or not wh.active:
        return None

    payload = json.dumps(delivery.payload, default=str).encode()
    signature = _sign_payload(wh.secret, payload)
    headers = {
        "Content-Type": "application/json",
        "X-CarbonScope-Signature": f"sha256={signature}",
        "X-CarbonScope-Event": delivery.event_type,
    }

    delivery.retry_count += 1
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(wh.url, content=payload, headers=headers)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        delivery.status_code = resp.status_code
        delivery.response_body = resp.text[:2048]
        delivery.success = resp.status_code < 400
        delivery.duration_ms = elapsed_ms
        delivery.error = None
    except (httpx.RequestError, httpx.TimeoutException, OSError) as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        delivery.duration_ms = elapsed_ms
        delivery.error = str(exc)[:2048]
        delivery.success = False

    if delivery.success:
        delivery.next_retry_at = None
    else:
        delay = _RETRY_DELAYS[min(delivery.retry_count, len(_RETRY_DELAYS) - 1)]
        delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

    await db.commit()
    await db.refresh(delivery)
    return delivery
