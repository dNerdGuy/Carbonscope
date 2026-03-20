"""Compliance reporting routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import RATE_LIMIT_DEFAULT
from api.database import get_db
from api.deps import get_current_user, require_credits
from api.limiter import limiter
from api.models import Company, EmissionReport, User
from api.schemas import ComplianceReportRequest
from api.services.compliance import (
    generate_cdp_responses,
    generate_csrd_report,
    generate_ghg_inventory,
    generate_issb_report,
    generate_sbti_pathway,
    generate_secr_report,
    generate_tcfd_disclosure,
)
from api.services.recommendations import generate_recommendations
from api.services.subscriptions import deduct_operation_credits
from api.services import audit

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/report")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def create_compliance_report(
    request: Request,
    body: ComplianceReportRequest,
    user: User = Depends(require_credits("estimate")),
    db: AsyncSession = Depends(get_db),
):
    """Generate a compliance report for a specific framework and emission report."""
    result = await db.execute(
        select(EmissionReport).where(
            EmissionReport.id == body.report_id,
            EmissionReport.company_id == user.company_id,
            EmissionReport.deleted_at.is_(None),
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    company_result = await db.execute(select(Company).where(Company.id == user.company_id, Company.deleted_at.is_(None)))
    company = company_result.scalar_one()

    # Generate report FIRST, then deduct credits only on success
    result = None
    if body.framework == "ghg_protocol":
        result = generate_ghg_inventory(
            company_name=company.name,
            industry=company.industry,
            region=company.region,
            year=report.year,
            scope1=report.scope1,
            scope2=report.scope2,
            scope3=report.scope3,
            total=report.total,
            breakdown=report.breakdown,
            sources=report.sources,
            assumptions=report.assumptions,
            confidence=report.confidence,
        )
    elif body.framework == "cdp":
        result = generate_cdp_responses(
            company_name=company.name,
            industry=company.industry,
            year=report.year,
            scope1=report.scope1,
            scope2=report.scope2,
            scope3=report.scope3,
            total=report.total,
            breakdown=report.breakdown,
            confidence=report.confidence,
        )
    elif body.framework == "tcfd":
        recs = generate_recommendations(
            emissions={"scope1": report.scope1, "scope2": report.scope2, "scope3": report.scope3, "total": report.total},
            breakdown=report.breakdown,
            industry=company.industry,
        )
        result = generate_tcfd_disclosure(
            company_name=company.name,
            industry=company.industry,
            year=report.year,
            scope1=report.scope1,
            scope2=report.scope2,
            scope3=report.scope3,
            total=report.total,
            recommendations=recs,
        )
    elif body.framework == "sbti":
        result = generate_sbti_pathway(
            company_name=company.name,
            year=report.year,
            scope1=report.scope1,
            scope2=report.scope2,
            scope3=report.scope3,
            total=report.total,
        )
    elif body.framework == "csrd":
        result = generate_csrd_report(
            company_name=company.name,
            industry=company.industry,
            region=company.region,
            year=report.year,
            scope1=report.scope1,
            scope2=report.scope2,
            scope3=report.scope3,
            total=report.total,
            breakdown=report.breakdown,
            sources=report.sources,
            assumptions=report.assumptions,
            confidence=report.confidence,
            employee_count=company.employee_count,
            revenue_usd=company.revenue_usd,
        )
    elif body.framework == "issb":
        recs = generate_recommendations(
            emissions={"scope1": report.scope1, "scope2": report.scope2, "scope3": report.scope3, "total": report.total},
            breakdown=report.breakdown,
            industry=company.industry,
        )
        result = generate_issb_report(
            company_name=company.name,
            industry=company.industry,
            region=company.region,
            year=report.year,
            scope1=report.scope1,
            scope2=report.scope2,
            scope3=report.scope3,
            total=report.total,
            breakdown=report.breakdown,
            sources=report.sources,
            confidence=report.confidence,
            employee_count=company.employee_count,
            revenue_usd=company.revenue_usd,
            recommendations=recs,
        )
    elif body.framework == "secr":
        result = generate_secr_report(
            company_name=company.name,
            industry=company.industry,
            region=company.region,
            year=report.year,
            scope1=report.scope1,
            scope2=report.scope2,
            scope3=report.scope3,
            total=report.total,
            breakdown=report.breakdown,
            sources=report.sources,
            confidence=report.confidence,
            employee_count=company.employee_count,
            revenue_usd=company.revenue_usd,
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown framework")

    # Report generated successfully — now deduct credits and record audit
    await deduct_operation_credits(db, user.company_id, "estimate")
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="generate", resource_type="compliance_report",
        resource_id=body.report_id, detail=f"framework: {body.framework}",
    )
    await db.commit()

    return result
