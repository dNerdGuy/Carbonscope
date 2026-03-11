"""AI-powered routes: text parsing, predictions, audit trail, recommendations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.models import Company, EmissionReport, User
from api.schemas import (
    AuditTrailRequest,
    ParseTextRequest,
    ParseTextResponse,
    PredictionRequest,
    PredictionResponse,
    RecommendationSummary,
)
from api.services.llm_parser import generate_audit_trail, parse_unstructured_text
from api.services.prediction import predict_missing_emissions
from api.services.recommendations import generate_recommendations, summarize_reduction_potential

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/parse-text", response_model=ParseTextResponse)
async def parse_text(
    body: ParseTextRequest,
    user: User = Depends(get_current_user),
):
    """Parse unstructured text (invoices, bills, etc.) into structured data."""
    extracted = await parse_unstructured_text(body.text)
    return ParseTextResponse(extracted_data=extracted)


@router.post("/predict", response_model=PredictionResponse)
async def predict(
    body: PredictionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Predict emissions for categories with missing data."""
    # Use company info as defaults
    result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = result.scalar_one()

    industry = body.industry or company.industry
    region = body.region or company.region

    prediction = predict_missing_emissions(body.known_data, industry, region)
    return PredictionResponse(**prediction)


@router.post("/audit-trail")
async def audit_trail(
    body: AuditTrailRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate an audit trail narrative for an emission report."""
    result = await db.execute(
        select(EmissionReport).where(
            EmissionReport.id == body.report_id,
            EmissionReport.company_id == user.company_id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    company_result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = company_result.scalar_one()

    text = await generate_audit_trail(
        company=company.name,
        industry=company.industry,
        year=report.year,
        scope1=report.scope1,
        scope2=report.scope2,
        scope3=report.scope3,
        total=report.total,
        breakdown=report.breakdown,
        assumptions=report.assumptions,
        sources=report.sources,
        confidence=report.confidence,
    )
    return {"audit_trail": text}


@router.get("/recommendations/{report_id}", response_model=RecommendationSummary)
async def get_recommendations(
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get carbon reduction recommendations based on a specific report."""
    result = await db.execute(
        select(EmissionReport).where(
            EmissionReport.id == report_id,
            EmissionReport.company_id == user.company_id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    company_result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = company_result.scalar_one()

    emissions = {
        "scope1": report.scope1,
        "scope2": report.scope2,
        "scope3": report.scope3,
        "total": report.total,
    }

    recs = generate_recommendations(
        emissions=emissions,
        breakdown=report.breakdown,
        industry=company.industry,
    )
    summary = summarize_reduction_potential(recs, report.total)

    return RecommendationSummary(recommendations=recs, summary=summary)
