"""Subscription & credit management service.

Handles plan tiers, credit ledger, and Stripe webhook processing.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import CreditLedger, Subscription, _utcnow

logger = logging.getLogger(__name__)

# ── Plan definitions ────────────────────────────────────────────────

PLAN_LIMITS: dict[str, dict[str, Any]] = {
    "free": {
        "monthly_credits": 100,
        "max_reports_per_month": 3,
        "max_scenarios": 5,
        "max_questionnaires": 3,
        "pdf_export": False,
        "supply_chain": False,
        "webhooks": False,
        "marketplace": False,
        "price_usd": 0,
    },
    "pro": {
        "monthly_credits": 1000,
        "max_reports_per_month": -1,  # unlimited
        "max_scenarios": -1,
        "max_questionnaires": -1,
        "pdf_export": True,
        "supply_chain": True,
        "webhooks": True,
        "marketplace": True,
        "price_usd": 99,
    },
    "enterprise": {
        "monthly_credits": 10000,
        "max_reports_per_month": -1,
        "max_scenarios": -1,
        "max_questionnaires": -1,
        "pdf_export": True,
        "supply_chain": True,
        "webhooks": True,
        "marketplace": True,
        "price_usd": 499,
    },
}

# Credit costs per operation
CREDIT_COSTS: dict[str, int] = {
    "estimate": 10,
    "pdf_export": 5,
    "questionnaire_extract": 5,
    "scenario_compute": 3,
    "marketplace_purchase": 0,  # uses listing price
}


async def get_or_create_subscription(db: AsyncSession, company_id: str) -> Subscription:
    """Get the active subscription for a company, or create a free one."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.company_id == company_id,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        sub = Subscription(company_id=company_id, plan="free", status="active")
        db.add(sub)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            result = await db.execute(
                select(Subscription).where(
                    Subscription.company_id == company_id,
                )
            )
            sub = result.scalar_one_or_none()
            if sub is None:
                raise
            return sub
        await grant_credits(db, company_id, PLAN_LIMITS["free"]["monthly_credits"], "subscription_grant")
    return sub


async def get_plan_limits(db: AsyncSession, company_id: str) -> dict[str, Any]:
    """Return the plan limits for a company."""
    sub = await get_or_create_subscription(db, company_id)
    return {"plan": sub.plan, **PLAN_LIMITS.get(sub.plan, PLAN_LIMITS["free"])}


async def change_plan(db: AsyncSession, company_id: str, new_plan: str) -> Subscription:
    """Change a company's subscription plan."""
    if new_plan not in PLAN_LIMITS:
        raise ValueError(f"Invalid plan: {new_plan}")

    sub = await get_or_create_subscription(db, company_id)
    old_plan = sub.plan
    if old_plan == new_plan:
        return sub

    sub.plan = new_plan
    sub.updated_at = _utcnow()

    old_credits = PLAN_LIMITS[old_plan]["monthly_credits"]
    new_credits = PLAN_LIMITS[new_plan]["monthly_credits"]

    if new_credits > old_credits:
        # Upgrade: grant the delta
        await grant_credits(db, company_id, new_credits - old_credits, "plan_upgrade")
    elif new_credits < old_credits:
        # Downgrade: cap balance to new plan's monthly limit
        current_balance = await get_credit_balance(db, company_id)
        if current_balance > new_credits:
            excess = current_balance - new_credits
            await deduct_credits(db, company_id, excess, "plan_downgrade_adjustment")

    await db.flush()
    return sub


async def get_credit_balance(db: AsyncSession, company_id: str) -> int:
    """Get the current credit balance for a company."""
    result = await db.execute(
        select(CreditLedger.balance_after)
        .where(CreditLedger.company_id == company_id)
        .order_by(CreditLedger.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row if row is not None else 0


async def _get_balance_for_update(db: AsyncSession, company_id: str) -> int:
    """Get current credit balance with row-level locking to prevent race conditions.

    Uses SELECT ... FOR UPDATE on PostgreSQL; on SQLite, serialized writes
    provide equivalent safety within the same connection.
    """
    from sqlalchemy import text

    # Get the latest ledger entry with lock
    result = await db.execute(
        select(CreditLedger)
        .where(CreditLedger.company_id == company_id)
        .order_by(CreditLedger.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    entry = result.scalar_one_or_none()
    return entry.balance_after if entry is not None else 0


async def _lock_subscription_for_credits(db: AsyncSession, company_id: str) -> None:
    """Lock the company subscription row to serialize credit mutations.

    Locking the subscription row avoids the empty-ledger race where two
    concurrent deductions could both observe the same latest balance.
    """
    await db.execute(
        select(Subscription.id)
        .where(Subscription.company_id == company_id)
        .limit(1)
        .with_for_update()
    )


async def grant_credits(db: AsyncSession, company_id: str, amount: int, reason: str) -> CreditLedger:
    """Add credits to a company's balance."""
    await _lock_subscription_for_credits(db, company_id)
    current = await _get_balance_for_update(db, company_id)
    entry = CreditLedger(
        company_id=company_id,
        amount=amount,
        reason=reason,
        balance_after=current + amount,
    )
    db.add(entry)
    await db.flush()
    return entry


async def deduct_credits(db: AsyncSession, company_id: str, amount: int, reason: str) -> CreditLedger:
    """Deduct credits from a company's balance. Raises ValueError if insufficient."""
    await _lock_subscription_for_credits(db, company_id)
    current = await _get_balance_for_update(db, company_id)
    if current < amount:
        raise ValueError(f"Insufficient credits: have {current}, need {amount}")
    entry = CreditLedger(
        company_id=company_id,
        amount=-amount,
        reason=reason,
        balance_after=current - amount,
    )
    db.add(entry)
    await db.flush()
    return entry


async def check_feature_access(db: AsyncSession, company_id: str, feature: str) -> bool:
    """Check if a company's plan allows a specific feature."""
    limits = await get_plan_limits(db, company_id)
    return limits.get(feature, False) is not False


async def check_credit_and_deduct(db: AsyncSession, company_id: str, operation: str) -> None:
    """Check credits and deduct for an operation. Raises ValueError if insufficient."""
    # Ensure subscription exists (auto-grants initial credits on first access)
    await get_or_create_subscription(db, company_id)
    cost = CREDIT_COSTS.get(operation, 0)
    if cost > 0:
        await deduct_credits(db, company_id, cost, f"{operation}_usage")


async def check_credit_balance(db: AsyncSession, company_id: str, operation: str) -> None:
    """Verify a company has enough credits for an operation without deducting.

    Raises ValueError if insufficient credits. Call deduct_credits separately
    after the operation succeeds to avoid credit loss on failure.
    """
    await get_or_create_subscription(db, company_id)
    cost = CREDIT_COSTS.get(operation, 0)
    if cost > 0:
        balance = await get_credit_balance(db, company_id)
        if balance < cost:
            raise ValueError(f"Insufficient credits: have {balance}, need {cost}")


async def deduct_operation_credits(db: AsyncSession, company_id: str, operation: str) -> None:
    """Deduct credits for a completed operation. Call after the operation succeeds."""
    cost = CREDIT_COSTS.get(operation, 0)
    if cost > 0:
        await deduct_credits(db, company_id, cost, f"{operation}_usage")
        await db.commit()


async def get_credit_ledger(
    db: AsyncSession, company_id: str, limit: int = 50, offset: int = 0,
) -> tuple[list[CreditLedger], int]:
    """Return paginated credit transaction history for a company."""
    base = select(CreditLedger).where(CreditLedger.company_id == company_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    result = await db.execute(
        base.order_by(CreditLedger.created_at.desc()).limit(limit).offset(offset)
    )
    return result.scalars().all(), total
