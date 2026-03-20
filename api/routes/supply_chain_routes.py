"""Supply chain network routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import RATE_LIMIT_DEFAULT
from api.database import get_db
from api.deps import get_current_user, require_admin
from api.limiter import limiter
from api.models import User

logger = logging.getLogger(__name__)
from api.schemas import PaginatedResponse, SupplyChainLinkCreate, SupplyChainLinkOut, SupplyChainLinkUpdate, SupplierListItem, BuyerListItem
from api.services.supply_chain import (
    calc_supplier_scope3,
    create_link,
    get_link as svc_get_link,
    list_buyers,
    list_suppliers,
    remove_link,
    update_link_status,
)
from api.services import audit
from api.services.webhooks import dispatch_event

router = APIRouter(prefix="/supply-chain", tags=["supply-chain"])


@router.post("/links", response_model=SupplyChainLinkOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def add_supplier(
    request: Request,
    body: SupplyChainLinkCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a supplier to the company's supply chain."""
    try:
        link = await create_link(
            db=db,
            buyer_company_id=user.company_id,
            supplier_company_id=body.supplier_company_id,
            spend_usd=body.spend_usd,
            category=body.category,
            notes=body.notes,
        )
        await dispatch_event(db, user.company_id, "supply_chain.link_created", {
            "link_id": link.id,
            "supplier_company_id": body.supplier_company_id,
            "category": body.category or "general",
        })
        return link
    except ValueError as e:
        logger.warning("Supply chain link creation failed: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid supplier link parameters")


@router.get("/suppliers", response_model=PaginatedResponse[SupplierListItem])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_suppliers(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all suppliers and their emission data."""
    items, total = await list_suppliers(db, user.company_id, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/buyers", response_model=PaginatedResponse[BuyerListItem])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_buyers(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all buyers this company supplies to."""
    items, total = await list_buyers(db, user.company_id, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/scope3-from-suppliers", response_model=dict)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def scope3_from_suppliers(
    request: Request,
    year: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Calculate Scope 3 Cat 1 emissions from verified supplier data."""
    return await calc_supplier_scope3(db, user.company_id, year)


@router.get("/links/{link_id}", response_model=SupplyChainLinkOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_link(
    request: Request,
    link_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific supply chain link."""
    link = await svc_get_link(db, link_id, user.company_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    return link


@router.patch("/links/{link_id}", response_model=SupplyChainLinkOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def update_link(
    request: Request,
    link_id: str,
    body: SupplyChainLinkUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a supply chain link's verification status."""
    link = await update_link_status(db, link_id, user.company_id, body.status)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="update", resource_type="supply_chain_link", resource_id=link_id,
    )
    if body.status == "verified":
        await dispatch_event(db, user.company_id, "supply_chain.link_verified", {
            "link_id": link_id,
            "status": "verified",
        })
    return link


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def delete_link(
    request: Request,
    link_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Remove a supply chain link (admin only)."""
    removed = await remove_link(db, link_id, user.company_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
