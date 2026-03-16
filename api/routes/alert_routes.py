"""Alert routes — listing, acknowledging, and triggering alert checks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import RATE_LIMIT_DEFAULT
from api.database import get_db
from api.deps import get_current_user, require_admin
from api.limiter import limiter
from api.models import User
from api.schemas import AlertOut, PaginatedResponse
from api.services.alerts import acknowledge_alert, check_company_alerts, list_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=PaginatedResponse[AlertOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_alerts(
    request: Request,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List alerts for the current company."""
    alerts, total = await list_alerts(
        db, user.company_id, unread_only=unread_only, limit=limit, offset=offset
    )
    return PaginatedResponse(items=alerts, total=total, limit=limit, offset=offset)


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def ack_alert(
    request: Request,
    alert_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge/mark an alert as read."""
    alert = await acknowledge_alert(db, alert_id, user.company_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    await db.commit()
    return alert


@router.post("/check", response_model=list[AlertOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def trigger_alert_check(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger alert checks for the current company."""
    new_alerts = await check_company_alerts(db, user.company_id)
    await db.commit()
    return new_alerts
