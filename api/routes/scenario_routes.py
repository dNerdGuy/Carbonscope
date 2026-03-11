"""What-if scenario routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.models import EmissionReport, Scenario, User
from api.schemas import PaginatedResponse, ScenarioCreate, ScenarioOut
from api.services.scenarios import run_scenario

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.post("/", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    body: ScenarioCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a what-if scenario linked to an emission report."""
    # Verify the base report belongs to the user's company
    result = await db.execute(
        select(EmissionReport).where(
            EmissionReport.id == body.base_report_id,
            EmissionReport.company_id == user.company_id,
            EmissionReport.deleted_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Base emission report not found",
        )

    scenario = Scenario(
        company_id=user.company_id,
        name=body.name,
        description=body.description,
        base_report_id=body.base_report_id,
        parameters=body.parameters,
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    return scenario


@router.get("/", response_model=PaginatedResponse[ScenarioOut])
async def list_scenarios(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List scenarios for the current user's company."""
    base = select(Scenario).where(Scenario.company_id == user.company_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(Scenario.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()

    return PaginatedResponse[ScenarioOut](
        items=[ScenarioOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{scenario_id}", response_model=ScenarioOut)
async def get_scenario(
    scenario_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific scenario."""
    result = await db.execute(
        select(Scenario).where(
            Scenario.id == scenario_id,
            Scenario.company_id == user.company_id,
        )
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return scenario


@router.post("/{scenario_id}/compute", response_model=ScenarioOut)
async def compute_scenario(
    scenario_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the what-if computation for a scenario."""
    try:
        scenario = await run_scenario(db, scenario_id, user.company_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return scenario


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a scenario."""
    result = await db.execute(
        select(Scenario).where(
            Scenario.id == scenario_id,
            Scenario.company_id == user.company_id,
        )
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    await db.delete(scenario)
    await db.commit()
