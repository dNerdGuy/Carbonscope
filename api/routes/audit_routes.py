"""Audit log routes — list audit entries for the current company."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import RATE_LIMIT_DEFAULT
from api.database import get_db
from api.deps import get_current_user, require_admin
from api.limiter import limiter
from api.models import User
from api.schemas import AuditLogOut, PaginatedResponse
from api.services.audit import list_logs

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("/", response_model=PaginatedResponse[AuditLogOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def list_audit_logs(
    request: Request,
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None, description="Filter logs from this date (ISO 8601)"),
    end_date: datetime | None = Query(default=None, description="Filter logs until this date (ISO 8601)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List audit log entries for the current user's company."""
    return await list_logs(
        db, company_id=user.company_id,
        action=action, resource_type=resource_type, user_id=user_id,
        start_date=start_date, end_date=end_date,
        limit=limit, offset=offset,
    )
