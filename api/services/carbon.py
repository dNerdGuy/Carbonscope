"""Carbon estimation & reporting service — business logic extracted from routes."""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Company, DataUpload, EmissionReport, _utcnow
from api.services import ServiceError

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_company(db: AsyncSession, company_id: str) -> Company:
    result = await db.execute(select(Company).where(Company.id == company_id, Company.deleted_at.is_(None)))
    return result.scalar_one()


async def _get_report(db: AsyncSession, report_id: str, company_id: str) -> EmissionReport:
    result = await db.execute(
        select(EmissionReport).where(
            EmissionReport.id == report_id,
            EmissionReport.company_id == company_id,
            EmissionReport.deleted_at.is_(None),
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise ServiceError("Report not found", status_code=404)
    return report


# ── Create estimate ──────────────────────────────────────────────────


async def create_estimate(
    db: AsyncSession,
    *,
    data_upload_id: str,
    company_id: str,
    user_id: str,
) -> EmissionReport:
    """Run an emission estimation against a data upload."""
    # Fetch the data upload (scoped to company)
    result = await db.execute(
        select(DataUpload).where(
            DataUpload.id == data_upload_id,
            DataUpload.company_id == company_id,
            DataUpload.deleted_at.is_(None),
        )
    )
    upload = result.scalar_one_or_none()
    if upload is None:
        raise ServiceError("Data upload not found", status_code=404)

    company = await _get_company(db, company_id)

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

    # Run estimation — local or subnet based on config
    from api.config import ESTIMATION_MODE
    from api.services.subnet_bridge import estimate_emissions, estimate_emissions_local

    if ESTIMATION_MODE == "subnet":
        try:
            est = await estimate_emissions(questionnaire)
        except RuntimeError:
            logger.warning("Subnet estimation failed, falling back to local estimation")
            est = estimate_emissions_local(questionnaire)
    else:
        est = estimate_emissions_local(questionnaire)

    emissions = est["emissions"]

    report = EmissionReport(
        company_id=company_id,
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

    # Deduct credits only after estimation succeeded
    from api.services.subscriptions import deduct_operation_credits
    await deduct_operation_credits(db, company_id, "estimate")

    # Record audit entry BEFORE commit so report + ledger + audit are atomic
    from api.services import audit
    await audit.record(
        db, user_id=user_id, company_id=company_id,
        action="create", resource_type="emission_report", resource_id=report.id,
    )

    await db.commit()
    await db.refresh(report)

    from api.services.webhooks import dispatch_event
    await dispatch_event(db, company_id, "report.created", {
        "report_id": report.id, "year": report.year, "total": report.total,
    })
    await dispatch_event(db, company_id, "estimate.completed", {
        "report_id": report.id, "year": report.year,
        "total": report.total, "confidence": report.confidence,
    })

    # Check for confidence improvement vs prior report for the same year
    prior = (await db.execute(
        select(EmissionReport.confidence)
        .where(
            EmissionReport.company_id == company_id,
            EmissionReport.year == report.year,
            EmissionReport.id != report.id,
            EmissionReport.deleted_at.is_(None),
        )
        .order_by(EmissionReport.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    if prior is not None and report.confidence > prior:
        await dispatch_event(db, company_id, "confidence.improved", {
            "report_id": report.id, "year": report.year,
            "old_confidence": round(prior, 4),
            "new_confidence": round(report.confidence, 4),
            "improvement": round(report.confidence - prior, 4),
        })

    return report


# ── Report CRUD ──────────────────────────────────────────────────────


async def list_reports(
    db: AsyncSession,
    company_id: str,
    *,
    year: int | None = None,
    confidence_min: float | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[EmissionReport], int]:
    base = select(EmissionReport).where(
        EmissionReport.company_id == company_id,
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
    return result.scalars().all(), total


async def get_report(db: AsyncSession, report_id: str, company_id: str) -> EmissionReport:
    return await _get_report(db, report_id, company_id)


async def update_report(
    db: AsyncSession,
    report_id: str,
    company_id: str,
    user_id: str,
    updates: dict[str, Any],
) -> EmissionReport:
    report = await _get_report(db, report_id, company_id)
    for key, value in updates.items():
        setattr(report, key, value)

    from api.services import audit
    await audit.record(
        db, user_id=user_id, company_id=company_id,
        action="update", resource_type="emission_report", resource_id=report_id,
    )
    await db.commit()
    await db.refresh(report)
    return report


async def delete_report(
    db: AsyncSession, report_id: str, company_id: str, user_id: str,
) -> None:
    report = await _get_report(db, report_id, company_id)
    report.deleted_at = _utcnow()
    from api.services import audit
    await audit.record(
        db, user_id=user_id, company_id=company_id,
        action="delete", resource_type="emission_report", resource_id=report_id,
    )
    await db.commit()


# ── Export ────────────────────────────────────────────────────────────


def _sanitize_csv(val: object) -> object:
    """Neutralise formula-injection prefixes for CSV export."""
    if isinstance(val, (int, float)) or val is None:
        return val
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


async def export_reports(
    db: AsyncSession,
    company_id: str,
    *,
    fmt: str = "csv",
    year: int | None = None,
) -> tuple[bytes, str, str]:
    """Export reports — returns (content_bytes, media_type, filename)."""
    base = select(EmissionReport).where(
        EmissionReport.company_id == company_id,
        EmissionReport.deleted_at.is_(None),
    )
    if year is not None:
        base = base.where(EmissionReport.year == year)

    result = await db.execute(base.order_by(EmissionReport.year.desc()))
    reports = result.scalars().all()

    if fmt == "json":
        data = [
            {
                "id": r.id,
                "year": r.year,
                "scope1": r.scope1,
                "scope2": r.scope2,
                "scope3": r.scope3,
                "total": r.total,
                "confidence": r.confidence,
                "methodology_version": r.methodology_version,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ]
        return json.dumps(data, indent=2).encode(), "application/json", "reports.json"

    if fmt == "parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:  # pragma: no cover
            raise ServiceError(500, "pyarrow is not installed — cannot export as Parquet") from exc

        table = pa.table({
            "id": pa.array([r.id for r in reports], type=pa.string()),
            "year": pa.array([r.year for r in reports], type=pa.int32()),
            "scope1": pa.array([r.scope1 for r in reports], type=pa.float64()),
            "scope2": pa.array([r.scope2 for r in reports], type=pa.float64()),
            "scope3": pa.array([r.scope3 for r in reports], type=pa.float64()),
            "total": pa.array([r.total for r in reports], type=pa.float64()),
            "confidence": pa.array([r.confidence for r in reports], type=pa.float64()),
            "methodology_version": pa.array([r.methodology_version for r in reports], type=pa.string()),
            "created_at": pa.array(
                [r.created_at.isoformat() if r.created_at else None for r in reports],
                type=pa.string(),
            ),
        })
        buf = io.BytesIO()
        pq.write_table(table, buf)
        return buf.getvalue(), "application/octet-stream", "reports.parquet"

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "year", "scope1", "scope2", "scope3", "total", "confidence", "methodology_version", "created_at"])
    for r in reports:
        writer.writerow([
            _sanitize_csv(r.id), r.year, r.scope1, r.scope2, r.scope3, r.total,
            r.confidence, _sanitize_csv(r.methodology_version),
            r.created_at.isoformat() if r.created_at else "",
        ])
    return output.getvalue().encode(), "text/csv", "reports.csv"


async def export_report_pdf(
    db: AsyncSession, report_id: str, company_id: str,
) -> tuple[bytes, int]:
    """Generate PDF for a report — returns (pdf_bytes, year)."""
    report = await _get_report(db, report_id, company_id)
    company = await _get_company(db, company_id)

    from api.services.subscriptions import deduct_operation_credits
    await deduct_operation_credits(db, company_id, "pdf_export")
    await db.commit()

    from api.services.pdf_export import generate_report_pdf
    pdf_bytes = generate_report_pdf(
        company_name=company.name,
        industry=company.industry,
        region=company.region,
        year=report.year,
        scope1=report.scope1,
        scope2=report.scope2,
        scope3=report.scope3,
        total=report.total,
        methodology=report.methodology_version,
        confidence=report.confidence,
    )
    return pdf_bytes, report.year


# ── Dashboard ────────────────────────────────────────────────────────


async def get_dashboard(db: AsyncSession, company_id: str) -> dict[str, Any]:
    """Build dashboard summary dict."""
    company = await _get_company(db, company_id)

    uploads_count = (
        await db.execute(
            select(func.count()).select_from(DataUpload).where(
                DataUpload.company_id == company_id,
                DataUpload.deleted_at.is_(None),
            )
        )
    ).scalar() or 0

    reports_count = (
        await db.execute(
            select(func.count()).select_from(EmissionReport).where(
                EmissionReport.company_id == company_id,
                EmissionReport.deleted_at.is_(None),
            )
        )
    ).scalar() or 0

    latest_result = await db.execute(
        select(EmissionReport)
        .where(
            EmissionReport.company_id == company_id,
            EmissionReport.deleted_at.is_(None),
        )
        .order_by(EmissionReport.created_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()

    latest_per_year = (
        select(
            EmissionReport.year,
            EmissionReport.scope1,
            EmissionReport.scope2,
            EmissionReport.scope3,
            EmissionReport.total,
            func.row_number()
            .over(
                partition_by=EmissionReport.year,
                order_by=EmissionReport.created_at.desc(),
            )
            .label("rn"),
        )
        .where(
            EmissionReport.company_id == company_id,
            EmissionReport.deleted_at.is_(None),
        )
        .subquery()
    )
    yoy_result = await db.execute(
        select(
            latest_per_year.c.year,
            latest_per_year.c.scope1,
            latest_per_year.c.scope2,
            latest_per_year.c.scope3,
            latest_per_year.c.total,
        )
        .where(latest_per_year.c.rn == 1)
        .order_by(latest_per_year.c.year)
    )
    yoy = [
        {"year": row.year, "scope1": row.scope1, "scope2": row.scope2, "scope3": row.scope3, "total": row.total}
        for row in yoy_result.all()
    ]

    return {
        "company": company,
        "latest": latest,
        "reports_count": reports_count,
        "uploads_count": uploads_count,
        "yoy": yoy,
    }
