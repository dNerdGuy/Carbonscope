"""Supply chain carbon network service.

Links buyer ↔ supplier companies so that a supplier's verified Scope 1+2
automatically feeds into the buyer's Scope 3 Category 1. Enables network-wide
emission propagation and data quality improvement.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

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
    """List all suppliers for a buyer, with their latest emissions if available."""
    result = await db.execute(
        select(SupplyChainLink, Company)
        .join(Company, Company.id == SupplyChainLink.supplier_company_id)
        .where(SupplyChainLink.buyer_company_id == buyer_company_id)
        .order_by(Company.name)
    )

    suppliers = []
    for link, company in result.all():
        # Get supplier's latest emission report
        report_result = await db.execute(
            select(EmissionReport)
            .where(EmissionReport.company_id == company.id)
            .order_by(EmissionReport.created_at.desc())
            .limit(1)
        )
        latest_report = report_result.scalar_one_or_none()

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
                "scope1": latest_report.scope1 if latest_report else None,
                "scope2": latest_report.scope2 if latest_report else None,
                "total": latest_report.total if latest_report else None,
                "confidence": latest_report.confidence if latest_report else None,
                "year": latest_report.year if latest_report else None,
            } if latest_report else None,
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
    """
    links_result = await db.execute(
        select(SupplyChainLink).where(
            SupplyChainLink.buyer_company_id == buyer_company_id,
            SupplyChainLink.status == "verified",
        )
    )
    links = links_result.scalars().all()

    if not links:
        return {
            "scope3_cat1_from_suppliers": 0.0,
            "supplier_count": 0,
            "verified_count": 0,
            "coverage_pct": 0.0,
            "details": [],
        }

    total_spend = sum(link.spend_usd or 0 for link in links)
    details = []
    cat1_total = 0.0

    for link in links:
        # Get supplier's latest report for the given year
        stmt = (
            select(EmissionReport)
            .where(EmissionReport.company_id == link.supplier_company_id)
            .order_by(EmissionReport.created_at.desc())
            .limit(1)
        )
        if year:
            stmt = stmt.where(EmissionReport.year == year)

        report_result = await db.execute(stmt)
        report = report_result.scalar_one_or_none()

        if report:
            # Supplier's Scope 1+2 = buyer's Scope 3 Cat 1
            supplier_emissions = report.scope1 + report.scope2

            # If spend data exists, attribute proportionally
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

    # Count total suppliers (including unverified) for coverage calc
    all_links_result = await db.execute(
        select(SupplyChainLink).where(
            SupplyChainLink.buyer_company_id == buyer_company_id
        )
    )
    all_count = len(all_links_result.scalars().all())

    return {
        "scope3_cat1_from_suppliers": round(cat1_total, 2),
        "supplier_count": all_count,
        "verified_count": len(links),
        "coverage_pct": round(len(links) / max(all_count, 1) * 100, 1),
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
