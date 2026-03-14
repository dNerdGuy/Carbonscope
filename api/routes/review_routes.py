"""Data review & approval workflow routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import RATE_LIMIT_DEFAULT
from api.database import get_db
from api.deps import get_current_user
from api.limiter import limiter
from api.models import User
from api.schemas import DataReviewAction, DataReviewCreate, DataReviewOut, PaginatedResponse
from api.services import audit
from api.services.reviews import ReviewError, create_review as svc_create, list_reviews as svc_list, get_review as svc_get, perform_action as svc_action

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("", response_model=DataReviewOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def create_review(
    request: Request,
    body: DataReviewCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a review record for an emission report (starts in 'draft')."""
    try:
        review = await svc_create(db, body.report_id, user.company_id)
    except ReviewError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    await db.commit()
    await db.refresh(review)
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="create", resource_type="data_review", resource_id=review.id,
    )
    await db.commit()
    return review


@router.get("", response_model=PaginatedResponse[DataReviewOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def list_reviews(
    request: Request,
    status_filter: str | None = None,
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List reviews for the current company, optionally filtered by status."""
    rows, total = await svc_list(db, user.company_id, status_filter=status_filter, limit=limit, offset=offset)
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/{review_id}", response_model=DataReviewOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_review(
    request: Request,
    review_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single review by ID."""
    try:
        return await svc_get(db, review_id, user.company_id)
    except ReviewError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/{review_id}/action", response_model=DataReviewOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def review_action(
    request: Request,
    review_id: str,
    body: DataReviewAction,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Perform an action on a review: submit, approve, or reject.

    State machine:
      draft -> submitted (by any member)
      submitted -> in_review (auto on approve/reject)
      submitted/in_review -> approved (admin only)
      submitted/in_review -> rejected (admin only)
    """
    try:
        review = await svc_get(db, review_id, user.company_id)
        review = await svc_action(db, review, body.action, user.id, user.role, notes=body.notes)
    except ReviewError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action=f"review_{body.action}", resource_type="data_review", resource_id=review.id,
        detail=body.notes,
    )
    await db.commit()
    await db.refresh(review)
    return review
