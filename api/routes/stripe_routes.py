"""Stripe webhook routes — process payment events from Stripe."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import async_session
from api.limiter import limiter
from api.models import Subscription

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["stripe"])

STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")


def _verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> dict:
    """Verify and parse Stripe webhook signature (v1 scheme).

    Stripe signs with HMAC-SHA256 over ``{timestamp}.{payload}``.
    We check that the signature is valid and the timestamp is not stale.
    """
    if not secret:
        raise ValueError("STRIPE_WEBHOOK_SECRET not configured")

    try:
        elements = {k: v for kv in sig_header.split(",") for k, v in [kv.split("=", 1)] if "=" in kv}
    except (ValueError, TypeError):
        raise ValueError("Invalid Stripe signature header")
    timestamp = elements.get("t")
    signature = elements.get("v1")

    if not timestamp or not signature:
        raise ValueError("Invalid Stripe signature header")

    # Reject timestamps older than 5 minutes to prevent replay attacks
    if abs(time.time() - int(timestamp)) > 300:
        raise ValueError("Stripe webhook timestamp too old")

    signed_payload = f"{timestamp}.".encode() + payload
    expected = hmac.new(
        secret.encode(), signed_payload, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise ValueError("Stripe signature verification failed")

    return json.loads(payload)


async def _handle_subscription_updated(data: dict) -> None:
    """Sync subscription status from Stripe."""
    stripe_sub = data.get("object", {})
    stripe_sub_id = stripe_sub.get("id")
    stripe_status = stripe_sub.get("status")

    if not stripe_sub_id:
        return

    status_map = {
        "active": "active",
        "past_due": "past_due",
        "canceled": "cancelled",
        "unpaid": "past_due",
    }
    new_status = status_map.get(stripe_status)
    if not new_status:
        logger.warning("Unknown Stripe subscription status: %s", stripe_status)
        return

    async with async_session() as db:
        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_sub_id,
            )
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            logger.warning("No subscription found for stripe_subscription_id=%s", stripe_sub_id)
            return

        sub.status = new_status
        await db.commit()
        logger.info(
            "Subscription %s updated status to %s (stripe_sub=%s)",
            sub.id, new_status, stripe_sub_id,
        )


async def _handle_invoice_payment_failed(data: dict) -> None:
    """Create an alert when a payment fails."""
    invoice = data.get("object", {})
    customer_id = invoice.get("customer")

    if not customer_id:
        return

    async with async_session() as db:
        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_customer_id == customer_id,
            )
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            logger.warning("No subscription found for stripe_customer_id=%s", customer_id)
            return

        # Mark as past_due
        sub.status = "past_due"

        # Create an alert for the company
        from api.models import Alert
        alert = Alert(
            company_id=sub.company_id,
            alert_type="target_exceeded",
            severity="critical",
            title="Payment Failed",
            message=(
                "Your subscription payment has failed. Please update your payment method "
                "to avoid service interruption."
            ),
            metadata_json={"stripe_customer_id": customer_id},
        )
        db.add(alert)
        await db.commit()

        # Send email notification
        from api.models import User
        user_result = await db.execute(
            select(User).where(
                User.company_id == sub.company_id,
                User.is_active.is_(True),
            ).limit(1)
        )
        user = user_result.scalar_one_or_none()
        if user:
            from api.services.email import send_alert_email
            await send_alert_email(
                user.email,
                "Payment Failed",
                "Your subscription payment has failed. Please update your payment method.",
                "critical",
            )

        logger.info("Payment failed alert created for company %s", sub.company_id)


async def _handle_checkout_session_completed(data: dict) -> None:
    """Link Stripe customer to subscription after initial checkout."""
    session = data.get("object", {})
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    company_id = session.get("metadata", {}).get("company_id")

    if not (customer_id and company_id):
        return

    async with async_session() as db:
        result = await db.execute(
            select(Subscription).where(
                Subscription.company_id == company_id,
            )
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            return

        sub.stripe_customer_id = customer_id
        if subscription_id:
            sub.stripe_subscription_id = subscription_id
        await db.commit()
        logger.info(
            "Linked Stripe customer %s to company %s", customer_id, company_id,
        )


# Event handler dispatch table
_EVENT_HANDLERS = {
    "customer.subscription.updated": _handle_subscription_updated,
    "customer.subscription.deleted": _handle_subscription_updated,
    "invoice.payment_failed": _handle_invoice_payment_failed,
    "checkout.session.completed": _handle_checkout_session_completed,
}


@router.post("/webhooks")
@limiter.limit("60/minute")
async def stripe_webhook(request: Request):
    """Receive and process Stripe webhook events.

    Verifies the Stripe-Signature header, parses the event,
    and dispatches to the appropriate handler.
    """
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhooks not configured",
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = _verify_stripe_signature(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError as e:
        logger.warning("Stripe webhook signature verification failed: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    event_type = event.get("type", "")
    event_data = event.get("data", {})

    handler = _EVENT_HANDLERS.get(event_type)
    if handler:
        try:
            await handler(event_data)
        except Exception:
            logger.exception("Error handling Stripe event %s", event_type)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook processing error",
            )
    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)

    return {"status": "ok"}
