"""Data marketplace routes — list, browse, and purchase anonymized emission data."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user, require_plan
from api.models import User
from api.schemas import (
    DataListingCreate,
    DataListingOut,
    DataPurchaseOut,
    PaginatedResponse,
)
from api.services.marketplace import browse_listings, create_listing, get_listing_by_id, list_my_listings, purchase_listing, withdraw_listing, list_my_sales, get_seller_revenue
from api.services import audit
from api.limiter import limiter
from api.config import RATE_LIMIT_DEFAULT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.post("/listings", response_model=DataListingOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def create_data_listing(
    request: Request,
    body: DataListingCreate,
    user: User = Depends(require_plan("marketplace")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new marketplace listing from one of your reports."""
    try:
        listing = await create_listing(
            db,
            company_id=user.company_id,
            title=body.title,
            description=body.description,
            data_type=body.data_type,
            report_id=body.report_id,
            price_credits=body.price_credits,
        )
        await db.commit()
        await db.refresh(listing)
        return listing
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/listings", response_model=PaginatedResponse[DataListingOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def browse_marketplace(
    request: Request,
    industry: str | None = Query(None),
    region: str | None = Query(None),
    data_type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Browse available marketplace listings."""
    listings, total = await browse_listings(
        db, industry=industry, region=region, data_type=data_type, limit=limit, offset=offset
    )
    return PaginatedResponse(items=listings, total=total, limit=limit, offset=offset)


@router.get("/listings/{listing_id}", response_model=DataListingOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_listing(
    request: Request,
    listing_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific marketplace listing."""
    listing = await get_listing_by_id(db, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return listing


@router.post("/listings/{listing_id}/purchase", response_model=DataPurchaseOut)
@limiter.limit("10/minute")
async def purchase_data(
    request: Request,
    listing_id: str,
    user: User = Depends(require_plan("marketplace")),
    db: AsyncSession = Depends(get_db),
):
    """Purchase a marketplace listing using credits."""
    try:
        purchase = await purchase_listing(db, listing_id, user.company_id)
        await db.commit()
        # Refresh with relationships loaded
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        from api.models import DataPurchase, DataListing, User as UserModel

        result = await db.execute(
            select(DataPurchase)
            .where(DataPurchase.id == purchase.id)
            .options(selectinload(DataPurchase.listing))
        )
        purchase = result.scalar_one()
        await audit.record(
            db, user_id=user.id, company_id=user.company_id,
            action="create", resource_type="data_purchase", resource_id=purchase.id,
        )

        # Send email notifications (best-effort, don't fail the purchase)
        try:
            from api.services.email_async import (
                send_marketplace_purchase_email,
                send_marketplace_sale_email,
            )
            listing = purchase.listing
            # Notify buyer
            await send_marketplace_purchase_email(
                user.email, listing.title, listing.price_credits, listing.data_type,
            )
            # Notify seller
            seller_result = await db.execute(
                select(UserModel).where(
                    UserModel.company_id == listing.seller_company_id,
                    UserModel.is_active.is_(True),
                ).limit(1)
            )
            seller_user = seller_result.scalar_one_or_none()
            if seller_user:
                await send_marketplace_sale_email(
                    seller_user.email, listing.title, listing.price_credits,
                )
        except Exception:
            logger.warning("Email notification failed for marketplace purchase %s", purchase.id)

        return purchase
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/my-listings", response_model=PaginatedResponse[DataListingOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_my_listings(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List your own marketplace listings."""
    listings, total = await list_my_listings(db, user.company_id, limit, offset)
    return PaginatedResponse(items=listings, total=total, limit=limit, offset=offset)


@router.post("/listings/{listing_id}/withdraw", response_model=DataListingOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def withdraw_data_listing(
    request: Request,
    listing_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Withdraw one of your listings from the marketplace."""
    listing = await withdraw_listing(db, listing_id, user.company_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found or already withdrawn")
    await db.commit()
    await db.refresh(listing)
    return listing


@router.get("/my-sales", response_model=PaginatedResponse[DataPurchaseOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_my_sales(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List purchases of your listings (seller view — who bought your data)."""
    sales, total = await list_my_sales(db, user.company_id, limit, offset)
    return PaginatedResponse(items=sales, total=total, limit=limit, offset=offset)


@router.get("/my-revenue")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_my_revenue(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get revenue summary from marketplace sales."""
    return await get_seller_revenue(db, user.company_id)
