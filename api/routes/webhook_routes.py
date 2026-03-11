"""Webhook management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.models import User
from api.schemas import WebhookCreate, WebhookOut
from api.services.webhooks import create_webhook, delete_webhook, list_webhooks, toggle_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
async def add_webhook(
    body: WebhookCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new webhook endpoint."""
    try:
        wh = await create_webhook(db, user.company_id, body.url, body.event_types)
        return wh
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=list[WebhookOut])
async def get_webhooks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all webhooks for the current company."""
    return await list_webhooks(db, user.company_id)


@router.patch("/{webhook_id}", response_model=WebhookOut)
async def update_webhook(
    webhook_id: str,
    active: bool = True,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable a webhook."""
    wh = await toggle_webhook(db, webhook_id, user.company_id, active)
    if not wh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return wh


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_webhook(
    webhook_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook."""
    removed = await delete_webhook(db, webhook_id, user.company_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
