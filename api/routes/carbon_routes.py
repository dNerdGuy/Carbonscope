"""Carbon estimation & reporting routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.models import Company, DataUpload, EmissionReport, User, _utcnow
from api.schemas import (
    DashboardSummary,
    CompanyOut,
    EmissionReportOut,
    EstimateRequest,
    PaginatedResponse,
)
from api.services.subnet_bridge import estimate_emissions_local

router = APIRouter(tags=["carbon"])


# ── Trigger estimation ──────────────────────────────────────────────


@router.post("/estimate", response_model=EmissionReportOut, status_code=status.HTTP_201_CREATED)
async def create_estimate(
    body: EstimateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run an emission estimation against a data upload.

    Uses local estimation engine (in development) or Bittensor subnet miners
    (in production).
    """
    # Fetch the data upload (scoped to user's company)
    result = await db.execute(
        select(DataUpload).where(
            DataUpload.id == body.data_upload_id,
            DataUpload.company_id == user.company_id,
            DataUpload.deleted_at.is_(None),
        )
    )
    upload = result.scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data upload not found")

    # Fetch company for industry/region context
    result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = result.scalar_one()

    questionnaire = {
        "company": company.name,
        "industry": company.industry,
        "services_used": [],
        "provided_data": upload.provided_data,
        "region": company.region,
        "year": upload.year,
    }

    # Enrich provided_data with company-level fields if missing
    pd = questionnaire["provided_data"]
    if company.employee_count and not pd.get("employee_count"):
        pd["employee_count"] = company.employee_count
    if company.revenue_usd and not pd.get("revenue_usd"):
        pd["revenue_usd"] = company.revenue_usd

    # Run estimation (local for now — swap to estimate_emissions() for subnet)
    est = estimate_emissions_local(questionnaire)

    emissions = est["emissions"]

    report = EmissionReport(
        company_id=user.company_id,
        data_upload_id=upload.id,
        year=upload.year,
        scope1=emissions["scope1"],
        scope2=emissions["scope2"],
        scope3=emissions["scope3"],
        total=emissions["total"],
        breakdown=est["breakdown"],
        confidence=est["confidence"],
        sources=est["sources"],
        assumptions=est["assumptions"],
        methodology_version=est.get("methodology_version", "ghg_protocol_v2025"),
        miner_scores=est.get("miner_scores"),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


# ── Reports ─────────────────────────────────────────────────────────


@router.get("/reports", response_model=PaginatedResponse[EmissionReportOut])
async def list_reports(
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
    base = select(EmissionReport).where(
        EmissionReport.company_id == user.company_id,
        EmissionReport.deleted_at.is_(None),
    )
    if year is not None:
        base = base.where(EmissionReport.year == year)
    if confidence_min is not None:
        base = base.where(EmissionReport.confidence >= confidence_min)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    sort_col = getattr(EmissionReport, sort_by)
    sort_expr = sort_col.asc() if order == "asc" else sort_col.desc()
    result = await db.execute(base.order_by(sort_expr).limit(limit).offset(offset))
    return PaginatedResponse(items=result.scalars().all(), total=total, limit=limit, offset=offset)


@router.get("/reports/{report_id}", response_model=EmissionReportOut)
async def get_report(
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific emission report."""
    result = await db.execute(
        select(EmissionReport).where(
            EmissionReport.id == report_id,
            EmissionReport.company_id == user.company_id,
            EmissionReport.deleted_at.is_(None),
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a specific emission report."""
    result = await db.execute(
        select(EmissionReport).where(
            EmissionReport.id == report_id,
            EmissionReport.company_id == user.company_id,
            EmissionReport.deleted_at.is_(None),
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    report.deleted_at = _utcnow()
    await db.commit()


# ── Dashboard ───────────────────────────────────────────────────────


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a summary dashboard for the current company."""
    # Company
    result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = result.scalar_one()

    # Counts
    uploads_count = (
        await db.execute(
            select(func.count()).select_from(DataUpload).where(
                DataUpload.company_id == user.company_id,
                DataUpload.deleted_at.is_(None),
            )
        )
    ).scalar() or 0

    reports_count = (
        await db.execute(
            select(func.count())
            .select_from(EmissionReport)
            .where(
                EmissionReport.company_id == user.company_id,
                EmissionReport.deleted_at.is_(None),
            )
        )
    ).scalar() or 0

    # Latest report
    latest_result = await db.execute(
        select(EmissionReport)
        .where(
            EmissionReport.company_id == user.company_id,
            EmissionReport.deleted_at.is_(None),
        )
        .order_by(EmissionReport.created_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()

    # Year-over-year totals
    yoy_result = await db.execute(
        select(
            EmissionReport.year,
            func.sum(EmissionReport.scope1).label("scope1"),
            func.sum(EmissionReport.scope2).label("scope2"),
            func.sum(EmissionReport.scope3).label("scope3"),
            func.sum(EmissionReport.total).label("total"),
        )
        .where(
            EmissionReport.company_id == user.company_id,
            EmissionReport.deleted_at.is_(None),
        )
        .group_by(EmissionReport.year)
        .order_by(EmissionReport.year)
    )
    yoy = [
        {"year": row.year, "scope1": row.scope1, "scope2": row.scope2, "scope3": row.scope3, "total": row.total}
        for row in yoy_result.all()
    ]

    return DashboardSummary(
        company=CompanyOut.model_validate(company),
        latest_report=EmissionReportOut.model_validate(latest) if latest else None,
        reports_count=reports_count,
        data_uploads_count=uploads_count,
        year_over_year=yoy,
    )
