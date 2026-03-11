"""Supply chain carbon network service.

Links buyer ↔ supplier companies so that a supplier's verified Scope 1+2
automatically feeds into the buyer's Scope 3 Category 1. Enables network-wide
emission propagation and data quality improvement.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from api.models import Company, EmissionReport, SupplyChainLink


# ── Link management ──────────────────────────────────────────────────


async def create_link(
    db: AsyncSession,
    buyer_company_id: str,
    supplier_company_id: str,
    spend_usd: float | None = None,
    category: str = "purchased_goods",
    notes: str | None = None,
) -> SupplyChainLink:
    """Create a buyer → supplier link."""
    if buyer_company_id == supplier_company_id:
        raise ValueError("A company cannot be its own supplier")

    # Check no duplicate
    existing = await db.execute(
        select(SupplyChainLink).where(
            SupplyChainLink.buyer_company_id == buyer_company_id,
            SupplyChainLink.supplier_company_id == supplier_company_id,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("Supply chain link already exists")

    link = SupplyChainLink(
        buyer_company_id=buyer_company_id,
        supplier_company_id=supplier_company_id,
        spend_usd=spend_usd,
        category=category,
        notes=notes,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def list_suppliers(
    db: AsyncSession,
    buyer_company_id: str,
) -> list[dict[str, Any]]:
    """List all suppliers for a buyer, with their latest emissions if available.

    Uses a single query with a correlated subquery to avoid N+1 performance issues.
    """
    # Subquery: latest report created_at per company
    latest_ts = (
        select(func.max(EmissionReport.created_at))
        .where(
            EmissionReport.company_id == SupplyChainLink.supplier_company_id,
            EmissionReport.deleted_at.is_(None),
        )
        .correlate(SupplyChainLink)
        .scalar_subquery()
    )

    LatestReport = aliased(EmissionReport)

    stmt = (
        select(SupplyChainLink, Company, LatestReport)
        .join(Company, Company.id == SupplyChainLink.supplier_company_id)
        .outerjoin(
            LatestReport,
            and_(
                LatestReport.company_id == SupplyChainLink.supplier_company_id,
                LatestReport.created_at == latest_ts,
                LatestReport.deleted_at.is_(None),
            ),
        )
        .where(SupplyChainLink.buyer_company_id == buyer_company_id)
        .order_by(Company.name)
    )

    result = await db.execute(stmt)

    suppliers = []
    for link, company, report in result.all():
        suppliers.append({
            "link_id": link.id,
            "company_id": company.id,
            "company_name": company.name,
            "industry": company.industry,
            "region": company.region,
            "spend_usd": link.spend_usd,
            "category": link.category,
            "status": link.status,
            "emissions": {
                "scope1": report.scope1 if report else None,
                "scope2": report.scope2 if report else None,
                "total": report.total if report else None,
                "confidence": report.confidence if report else None,
                "year": report.year if report else None,
            } if report else None,
            "created_at": link.created_at.isoformat(),
        })

    return suppliers


async def list_buyers(
    db: AsyncSession,
    supplier_company_id: str,
) -> list[dict[str, Any]]:
    """List all buyers that this company supplies."""
    result = await db.execute(
        select(SupplyChainLink, Company)
        .join(Company, Company.id == SupplyChainLink.buyer_company_id)
        .where(SupplyChainLink.supplier_company_id == supplier_company_id)
        .order_by(Company.name)
    )

    return [
        {
            "link_id": link.id,
            "company_id": company.id,
            "company_name": company.name,
            "industry": company.industry,
            "spend_usd": link.spend_usd,
            "category": link.category,
            "status": link.status,
            "created_at": link.created_at.isoformat(),
        }
        for link, company in result.all()
    ]


async def calc_supplier_scope3(
    db: AsyncSession,
    buyer_company_id: str,
    year: int | None = None,
) -> dict[str, Any]:
    """Calculate Scope 3 Category 1 from verified supplier emissions.

    For each linked supplier, their Scope 1+2 is attributed to the buyer's
    Scope 3 Cat 1, weighted by spend allocation.
    Uses a single query with LEFT JOIN to avoid N+1 issues.
    """
    # Subquery: latest report per supplier (filtered by year if given)
    report_filter = [
        EmissionReport.deleted_at.is_(None),
    ]
    if year:
        report_filter.append(EmissionReport.year == year)

    latest_ts_sub = (
        select(func.max(EmissionReport.created_at))
        .where(
            EmissionReport.company_id == SupplyChainLink.supplier_company_id,
            *report_filter,
        )
        .correlate(SupplyChainLink)
        .scalar_subquery()
    )

    LatestReport = aliased(EmissionReport)

    stmt = (
        select(SupplyChainLink, LatestReport)
        .outerjoin(
            LatestReport,
            and_(
                LatestReport.company_id == SupplyChainLink.supplier_company_id,
                LatestReport.created_at == latest_ts_sub,
                LatestReport.deleted_at.is_(None),
                *([LatestReport.year == year] if year else []),
            ),
        )
        .where(
            SupplyChainLink.buyer_company_id == buyer_company_id,
            SupplyChainLink.status == "verified",
        )
    )

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        # Count all links for coverage calc
        all_count_r = await db.execute(
            select(func.count()).select_from(SupplyChainLink).where(
                SupplyChainLink.buyer_company_id == buyer_company_id
            )
        )
        all_count = all_count_r.scalar() or 0
        return {
            "scope3_cat1_from_suppliers": 0.0,
            "supplier_count": all_count,
            "verified_count": 0,
            "coverage_pct": 0.0,
            "details": [],
        }

    total_spend = sum(link.spend_usd or 0 for link, _ in rows)
    details = []
    cat1_total = 0.0

    for link, report in rows:
        if report:
            supplier_emissions = report.scope1 + report.scope2

            if link.spend_usd and total_spend > 0:
                attribution = link.spend_usd / total_spend
                attributed = supplier_emissions * attribution
            else:
                attributed = supplier_emissions

            cat1_total += attributed
            details.append({
                "supplier_company_id": link.supplier_company_id,
                "supplier_scope1": report.scope1,
                "supplier_scope2": report.scope2,
                "attributed_tco2e": round(attributed, 2),
                "spend_usd": link.spend_usd,
                "year": report.year,
                "confidence": report.confidence,
            })

    # Count total suppliers for coverage calc
    all_count_r = await db.execute(
        select(func.count()).select_from(SupplyChainLink).where(
            SupplyChainLink.buyer_company_id == buyer_company_id
        )
    )
    all_count = all_count_r.scalar() or 0

    return {
        "scope3_cat1_from_suppliers": round(cat1_total, 2),
        "supplier_count": all_count,
        "verified_count": len(rows),
        "coverage_pct": round(len(rows) / max(all_count, 1) * 100, 1),
        "details": details,
    }


async def remove_link(
    db: AsyncSession,
    link_id: str,
    company_id: str,
) -> bool:
    """Remove a supply chain link (only if the requester is the buyer)."""
    result = await db.execute(
        select(SupplyChainLink).where(
            SupplyChainLink.id == link_id,
            SupplyChainLink.buyer_company_id == company_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        return False

    await db.delete(link)
    await db.commit()
    return True


async def update_link_status(
    db: AsyncSession,
    link_id: str,
    company_id: str,
    status: str,
) -> SupplyChainLink | None:
    """Update the verification status of a supply chain link."""
    result = await db.execute(
        select(SupplyChainLink).where(
            SupplyChainLink.id == link_id,
            SupplyChainLink.buyer_company_id == company_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        return None

    link.status = status
    await db.commit()
    await db.refresh(link)
    return link
