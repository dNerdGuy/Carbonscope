"""PCAF financed emissions portfolio routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import RATE_LIMIT_DEFAULT
from api.database import get_db
from api.deps import get_current_user, require_plan
from api.limiter import limiter
from api.models import FinancedAsset, FinancedPortfolio, User
from api.schemas import (
    FinancedAssetCreate,
    FinancedAssetOut,
    FinancedPortfolioCreate,
    FinancedPortfolioOut,
    PaginatedResponse,
    PortfolioSummary,
)
from api.services.pcaf import calculate_financed_emissions, summarise_portfolio
from api.services import audit

router = APIRouter(prefix="/pcaf", tags=["pcaf"])


# ── Portfolios ──────────────────────────────────────────────────────


@router.post("/portfolios", response_model=FinancedPortfolioOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def create_portfolio(
    request: Request,
    body: FinancedPortfolioCreate,
    user: User = Depends(require_plan("supply_chain")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new financed-emissions portfolio."""
    portfolio = FinancedPortfolio(
        company_id=user.company_id,
        name=body.name,
        year=body.year,
    )
    db.add(portfolio)
    await db.flush()
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="create", resource_type="pcaf_portfolio", resource_id=portfolio.id,
    )
    await db.commit()
    await db.refresh(portfolio)
    return portfolio


@router.get("/portfolios", response_model=PaginatedResponse[FinancedPortfolioOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def list_portfolios(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List portfolios for the current company."""
    base = select(FinancedPortfolio).where(
        FinancedPortfolio.company_id == user.company_id,
        FinancedPortfolio.deleted_at.is_(None),
    )
    total_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(total_q)).scalar() or 0
    rows = (await db.execute(base.order_by(FinancedPortfolio.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/portfolios/{portfolio_id}/summary", response_model=PortfolioSummary)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def portfolio_summary(
    request: Request,
    portfolio_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated PCAF summary for a portfolio."""
    portfolio = await _get_portfolio(db, portfolio_id, user.company_id)
    result = await db.execute(
        select(FinancedAsset).where(FinancedAsset.portfolio_id == portfolio_id)
    )
    assets = result.scalars().all()
    asset_dicts = [
        {
            "outstanding_amount": a.outstanding_amount,
            "financed_emissions_tco2e": a.financed_emissions_tco2e,
            "data_quality_score": a.data_quality_score,
            "asset_class": a.asset_class,
        }
        for a in assets
    ]
    summary = summarise_portfolio(asset_dicts)
    return {
        "portfolio": portfolio,
        **summary,
    }


# ── Assets ──────────────────────────────────────────────────────────


@router.post("/portfolios/{portfolio_id}/assets", response_model=FinancedAssetOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def add_asset(
    request: Request,
    portfolio_id: str,
    body: FinancedAssetCreate,
    user: User = Depends(require_plan("supply_chain")),
    db: AsyncSession = Depends(get_db),
):
    """Add an asset to a PCAF portfolio and auto-calculate financed emissions."""
    await _get_portfolio(db, portfolio_id, user.company_id)

    af, fe = calculate_financed_emissions(
        body.outstanding_amount, body.total_equity_debt, body.investee_emissions_tco2e,
    )

    asset = FinancedAsset(
        portfolio_id=portfolio_id,
        asset_name=body.asset_name,
        asset_class=body.asset_class,
        outstanding_amount=body.outstanding_amount,
        total_equity_debt=body.total_equity_debt,
        investee_emissions_tco2e=body.investee_emissions_tco2e,
        attribution_factor=round(af, 6),
        financed_emissions_tco2e=fe,
        data_quality_score=body.data_quality_score,
        industry=body.industry,
        region=body.region,
        notes=body.notes,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="create", resource_type="pcaf_asset", resource_id=asset.id,
    )
    await db.commit()
    return asset


@router.get("/portfolios/{portfolio_id}/assets", response_model=PaginatedResponse[FinancedAssetOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def list_assets(
    request: Request,
    portfolio_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List assets in a portfolio."""
    await _get_portfolio(db, portfolio_id, user.company_id)
    base = select(FinancedAsset).where(FinancedAsset.portfolio_id == portfolio_id)
    total_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(total_q)).scalar() or 0
    rows = (await db.execute(base.order_by(FinancedAsset.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.delete("/portfolios/{portfolio_id}/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def delete_asset(
    request: Request,
    portfolio_id: str,
    asset_id: str,
    user: User = Depends(require_plan("supply_chain")),
    db: AsyncSession = Depends(get_db),
):
    """Remove an asset from a portfolio."""
    await _get_portfolio(db, portfolio_id, user.company_id)
    result = await db.execute(
        select(FinancedAsset).where(
            FinancedAsset.id == asset_id,
            FinancedAsset.portfolio_id == portfolio_id,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    await db.delete(asset)
    await db.commit()
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="delete", resource_type="pcaf_asset", resource_id=asset_id,
    )
    await db.commit()


# ── Helpers ─────────────────────────────────────────────────────────


async def _get_portfolio(db: AsyncSession, portfolio_id: str, company_id: str) -> FinancedPortfolio:
    result = await db.execute(
        select(FinancedPortfolio).where(
            FinancedPortfolio.id == portfolio_id,
            FinancedPortfolio.company_id == company_id,
            FinancedPortfolio.deleted_at.is_(None),
        )
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    return portfolio
