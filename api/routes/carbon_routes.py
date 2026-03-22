"""Carbon estimation & reporting routes."""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import RATE_LIMIT_DEFAULT
from api.database import get_db
from api.deps import get_current_user, require_credits, require_plan
from api.limiter import limiter
from api.models import User
from api.schemas import (
    CompanyOut,
    DashboardSummary,
    EmissionReportOut,
    EstimateRequest,
    PaginatedResponse,
    ReportUpdate,
)
from api.services import ServiceError
from api.services import carbon as carbon_svc

router = APIRouter(tags=["carbon"])


# ── Trigger estimation ──────────────────────────────────────────────


@router.post("/estimate", response_model=EmissionReportOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_estimate(
    request: Request,
    body: EstimateRequest,
    user: User = Depends(require_credits("estimate")),
    db: AsyncSession = Depends(get_db),
):
    """Run an emission estimation against a data upload."""
    try:
        report = await carbon_svc.create_estimate(
            db, data_upload_id=body.data_upload_id,
            company_id=user.company_id, user_id=user.id,
        )
    except ServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return report


# ── Reports ─────────────────────────────────────────────────────────


@router.get("/reports", response_model=PaginatedResponse[EmissionReportOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def list_reports(
    request: Request,
    year: int | None = Query(default=None),
    confidence_min: float | None = Query(default=None, ge=0, le=1),
    sort_by: str = Query(default="created_at", pattern="^(created_at|year|total|confidence)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List emission reports with pagination, filtering, and sorting."""
    items, total = await carbon_svc.list_reports(
        db, user.company_id,
        year=year, confidence_min=confidence_min,
        sort_by=sort_by, order=order, limit=limit, offset=offset,
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


# ── Export (must be before /reports/{report_id} so FastAPI matches it) ──


@router.get("/reports/export")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def export_reports(
    request: Request,
    format: str = Query(default="csv", pattern="^(csv|json|parquet)$"),
    year: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export emission reports as CSV or JSON."""
    content, media_type, filename = await carbon_svc.export_reports(
        db, user.company_id, fmt=format, year=year,
    )
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/reports/{report_id}", response_model=EmissionReportOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_report(
    request: Request,
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific emission report."""
    try:
        return await carbon_svc.get_report(db, report_id, user.company_id)
    except ServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.patch("/reports/{report_id}", response_model=EmissionReportOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def update_report(
    request: Request,
    report_id: str,
    body: ReportUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a report's year or notes."""
    try:
        return await carbon_svc.update_report(
            db, report_id, user.company_id, user.id,
            body.model_dump(exclude_unset=True),
        )
    except ServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/reports/{report_id}/export/pdf")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def export_report_pdf(
    request: Request,
    report_id: str,
    user: User = Depends(require_credits("pdf_export")),
    db: AsyncSession = Depends(get_db),
):
    """Export an emission report as a styled PDF."""
    try:
        pdf_bytes, year = await carbon_svc.export_report_pdf(db, report_id, user.company_id)
    except ServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=emission_report_{year}.pdf"},
    )


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def delete_report(
    request: Request,
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a specific emission report."""
    try:
        await carbon_svc.delete_report(db, report_id, user.company_id, user.id)
    except ServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# ── Dashboard ───────────────────────────────────────────────────────


@router.get("/dashboard", response_model=DashboardSummary)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a summary dashboard for the current company."""
    data = await carbon_svc.get_dashboard(db, user.company_id)
    return DashboardSummary(
        company=CompanyOut.model_validate(data["company"]),
        latest_report=EmissionReportOut.model_validate(data["latest"]) if data["latest"] else None,
        reports_count=data["reports_count"],
        data_uploads_count=data["uploads_count"],
        year_over_year=data["yoy"],
    )
