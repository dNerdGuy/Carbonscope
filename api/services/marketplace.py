"""Data marketplace service — anonymize, list, browse, and purchase emission data."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Company, DataListing, DataPurchase, EmissionReport
from api.services.subscriptions import deduct_credits, grant_credits

logger = logging.getLogger(__name__)


def _anonymize_report(report: EmissionReport, company: Company) -> dict[str, Any]:
    """Strip identifying info; keep emission metrics and industry context."""
    return {
        "industry": company.industry,
        "region": company.region,
        "year": report.year,
        "scope1": round(report.scope1, 1),
        "scope2": round(report.scope2, 1),
        "scope3": round(report.scope3, 1),
        "total": round(report.total, 1),
        "confidence": round(report.confidence, 2),
        "methodology_version": report.methodology_version,
        "breakdown_categories": list((report.breakdown or {}).keys()),
    }


async def create_listing(
    db: AsyncSession,
    company_id: str,
    title: str,
    description: str | None,
    data_type: str,
    report_id: str,
    price_credits: int,
) -> DataListing:
    """Create a new marketplace listing from a report."""
    # Verify the report belongs to the company
    result = await db.execute(
        select(EmissionReport).where(
            EmissionReport.id == report_id,
            EmissionReport.company_id == company_id,
            EmissionReport.deleted_at.is_(None),
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise ValueError("Report not found or not owned by company")

    # Get company for anonymization
    result = await db.execute(select(Company).where(Company.id == company_id, Company.deleted_at.is_(None)))
    company = result.scalar_one()

    listing = DataListing(
        seller_company_id=company_id,
        title=title,
        description=description,
        data_type=data_type,
        industry=company.industry,
        region=company.region,
        year=report.year,
        price_credits=price_credits,
        anonymized_data=_anonymize_report(report, company),
    )
    db.add(listing)
    await db.flush()
    return listing


async def browse_listings(
    db: AsyncSession,
    *,
    industry: str | None = None,
    region: str | None = None,
    data_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[DataListing], int]:
    """Browse available marketplace listings with optional filters."""
    query = select(DataListing).where(DataListing.status == "active", DataListing.deleted_at.is_(None))
    count_query = select(func.count()).select_from(DataListing).where(DataListing.status == "active", DataListing.deleted_at.is_(None))

    if industry:
        query = query.where(DataListing.industry == industry)
        count_query = count_query.where(DataListing.industry == industry)
    if region:
        query = query.where(DataListing.region == region)
        count_query = count_query.where(DataListing.region == region)
    if data_type:
        query = query.where(DataListing.data_type == data_type)
        count_query = count_query.where(DataListing.data_type == data_type)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(DataListing.created_at.desc()).offset(offset).limit(limit)
    )
    return result.scalars().all(), total


async def get_listing_by_id(db: AsyncSession, listing_id: str) -> DataListing | None:
    """Get a single active listing by ID."""
    result = await db.execute(
        select(DataListing).where(
            DataListing.id == listing_id,
            DataListing.status == "active",
            DataListing.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def purchase_listing(
    db: AsyncSession,
    listing_id: str,
    buyer_company_id: str,
) -> DataPurchase:
    """Purchase a marketplace listing using credits."""
    # Fetch the listing with row-level lock to prevent double-purchase race
    result = await db.execute(
        select(DataListing)
        .where(
            DataListing.id == listing_id,
            DataListing.status == "active",
            DataListing.deleted_at.is_(None),
        )
        .with_for_update()
    )
    listing = result.scalar_one_or_none()
    if listing is None:
        raise ValueError("Listing not found or no longer available")

    if listing.seller_company_id == buyer_company_id:
        raise ValueError("Cannot purchase your own listing")

    # Check existing purchase
    existing = await db.execute(
        select(DataPurchase).where(
            DataPurchase.listing_id == listing_id,
            DataPurchase.buyer_company_id == buyer_company_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("Already purchased this listing")

    purchase = DataPurchase(
        listing_id=listing_id,
        buyer_company_id=buyer_company_id,
        price_credits=listing.price_credits,
    )
    db.add(purchase)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ValueError("Already purchased this listing")

    # Only mutate credits after purchase uniqueness is validated.
    if listing.price_credits > 0:
        await deduct_credits(db, buyer_company_id, listing.price_credits, "marketplace_purchase_usage")
        await grant_credits(db, listing.seller_company_id, listing.price_credits, "marketplace_sale")
    return purchase


async def list_my_listings(
    db: AsyncSession,
    company_id: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[DataListing], int]:
    """List marketplace listings owned by a company."""
    query = select(DataListing).where(DataListing.seller_company_id == company_id, DataListing.deleted_at.is_(None))
    count_query = select(func.count()).select_from(DataListing).where(
        DataListing.seller_company_id == company_id, DataListing.deleted_at.is_(None)
    )
    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(DataListing.created_at.desc()).offset(offset).limit(limit)
    )
    return result.scalars().all(), total


async def withdraw_listing(
    db: AsyncSession,
    listing_id: str,
    company_id: str,
) -> DataListing | None:
    """Withdraw a listing from the marketplace (seller only)."""
    result = await db.execute(
        select(DataListing).where(
            DataListing.id == listing_id,
            DataListing.seller_company_id == company_id,
            DataListing.status == "active",
            DataListing.deleted_at.is_(None),
        )
    )
    listing = result.scalar_one_or_none()
    if listing is None:
        return None
    listing.status = "withdrawn"
    await db.flush()
    return listing


async def list_my_sales(
    db: AsyncSession,
    company_id: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[DataPurchase], int]:
    """List purchases of my listings (seller view — who bought my data)."""
    from sqlalchemy.orm import selectinload

    query = (
        select(DataPurchase)
        .join(DataListing, DataPurchase.listing_id == DataListing.id)
        .where(DataListing.seller_company_id == company_id)
        .options(selectinload(DataPurchase.listing))
    )
    count_query = (
        select(func.count())
        .select_from(DataPurchase)
        .join(DataListing, DataPurchase.listing_id == DataListing.id)
        .where(DataListing.seller_company_id == company_id)
    )
    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(DataPurchase.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def get_seller_revenue(db: AsyncSession, company_id: str) -> dict:
    """Get total revenue earned from marketplace sales."""
    total_revenue = (
        await db.execute(
            select(func.coalesce(func.sum(DataPurchase.price_credits), 0))
            .join(DataListing, DataPurchase.listing_id == DataListing.id)
            .where(DataListing.seller_company_id == company_id)
        )
    ).scalar() or 0

    total_sales = (
        await db.execute(
            select(func.count())
            .select_from(DataPurchase)
            .join(DataListing, DataPurchase.listing_id == DataListing.id)
            .where(DataListing.seller_company_id == company_id)
        )
    ).scalar() or 0

    active_listings = (
        await db.execute(
            select(func.count())
            .select_from(DataListing)
            .where(
                DataListing.seller_company_id == company_id,
                DataListing.status == "active",
            )
        )
    ).scalar() or 0

    return {
        "total_revenue_credits": total_revenue,
        "total_sales": total_sales,
        "active_listings": active_listings,
    }
