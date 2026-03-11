"""Supply chain network routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.models import User
from api.schemas import SupplyChainLinkCreate, SupplyChainLinkOut, SupplyChainLinkUpdate
from api.services.supply_chain import (
    calc_supplier_scope3,
    create_link,
    list_buyers,
    list_suppliers,
    remove_link,
    update_link_status,
)

router = APIRouter(prefix="/supply-chain", tags=["supply-chain"])


@router.post("/links", response_model=SupplyChainLinkOut, status_code=status.HTTP_201_CREATED)
async def add_supplier(
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
        return link
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/suppliers")
async def get_suppliers(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all suppliers and their emission data."""
    return await list_suppliers(db, user.company_id)


@router.get("/buyers")
async def get_buyers(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all buyers this company supplies to."""
    return await list_buyers(db, user.company_id)


@router.get("/scope3-from-suppliers")
async def scope3_from_suppliers(
    year: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Calculate Scope 3 Cat 1 emissions from verified supplier data."""
    return await calc_supplier_scope3(db, user.company_id, year)


@router.patch("/links/{link_id}", response_model=SupplyChainLinkOut)
async def update_link(
    link_id: str,
    body: SupplyChainLinkUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a supply chain link's verification status."""
    link = await update_link_status(db, link_id, user.company_id, body.status)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    return link


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    link_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a supply chain link."""
    removed = await remove_link(db, link_id, user.company_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
