"""Audit logging helper — records sensitive operations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import AuditLog


async def record(
    db: AsyncSession,
    *,
    user_id: str,
    company_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    detail: str | None = None,
) -> None:
    """Write an audit log entry (non-blocking — piggybacks on the caller's commit)."""
    db.add(
        AuditLog(
            user_id=user_id,
            company_id=company_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
        )
    )


async def list_logs(
    db: AsyncSession,
    *,
    company_id: str,
    action: str | None = None,
    resource_type: str | None = None,
    user_id: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List audit log entries for a company with optional filters and pagination."""
    base = select(AuditLog).where(AuditLog.company_id == company_id)
    if action is not None:
        base = base.where(AuditLog.action == action)
    if resource_type is not None:
        base = base.where(AuditLog.resource_type == resource_type)
    if user_id is not None:
        base = base.where(AuditLog.user_id == user_id)
    if start_date is not None:
        base = base.where(AuditLog.created_at >= start_date)
    if end_date is not None:
        base = base.where(AuditLog.created_at <= end_date)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    )).scalars().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}
