"""Webhook management routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import RATE_LIMIT_DEFAULT
from api.database import get_db
from api.deps import get_current_user, require_admin
from api.limiter import limiter
from api.models import User
from api.schemas import PaginatedResponse, WebhookCreate, WebhookDeliveryOut, WebhookOut, WebhookOutPublic, WebhookToggle
from api.services.webhooks import create_webhook, delete_webhook, list_deliveries, list_webhooks, retry_delivery, toggle_webhook
from api.services import audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def add_webhook(
    request: Request,
    body: WebhookCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Register a new webhook endpoint."""
    try:
        wh = await create_webhook(db, user.company_id, body.url, body.event_types)
        await audit.record(
            db, user_id=user.id, company_id=user.company_id,
            action="create", resource_type="webhook", resource_id=wh.id,
        )
        return wh
    except ValueError as e:
        logger.warning("Webhook creation failed: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook configuration")


@router.get("/", response_model=PaginatedResponse[WebhookOutPublic])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_webhooks(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all webhooks for the current company."""
    items, total = await list_webhooks(db, user.company_id, limit=limit, offset=offset)
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.patch("/{webhook_id}", response_model=WebhookOutPublic)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def update_webhook(
    request: Request,
    webhook_id: str,
    body: WebhookToggle,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable a webhook."""
    wh = await toggle_webhook(db, webhook_id, user.company_id, body.active)
    if not wh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="update", resource_type="webhook", resource_id=webhook_id,
    )
    return wh


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def remove_webhook(
    request: Request,
    webhook_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook."""
    removed = await delete_webhook(db, webhook_id, user.company_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="delete", resource_type="webhook", resource_id=webhook_id,
    )


@router.get("/{webhook_id}/deliveries", response_model=PaginatedResponse[WebhookDeliveryOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_deliveries(
    request: Request,
    webhook_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List delivery logs for a webhook."""
    items, total = await list_deliveries(db, webhook_id, user.company_id, limit, offset)
    if total == 0:
        # Could be webhook not found — check ownership
        from sqlalchemy import select
        from api.models import Webhook

        result = await db.execute(
            select(Webhook).where(Webhook.id == webhook_id, Webhook.company_id == user.company_id, Webhook.deleted_at.is_(None))
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/{webhook_id}/deliveries/{delivery_id}/retry", response_model=WebhookDeliveryOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def retry_webhook_delivery(
    request: Request,
    webhook_id: str,
    delivery_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Manually retry a failed webhook delivery."""
    delivery = await retry_delivery(db, delivery_id, user.company_id)
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="retry", resource_type="webhook_delivery", resource_id=delivery_id,
    )
    return delivery
