"""What-if scenario routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user, require_credits
from api.models import User
from api.schemas import PaginatedResponse, ScenarioCreate, ScenarioOut, ScenarioUpdate
from api.services import audit
from api.services.scenarios import (
    ScenarioError,
    create_scenario as svc_create,
    delete_scenario as svc_delete,
    get_scenario as svc_get,
    list_scenarios as svc_list,
    run_scenario,
    update_scenario as svc_update,
)
from api.limiter import limiter
from api.config import RATE_LIMIT_DEFAULT

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.post("/", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def create_scenario(
    request: Request,
    body: ScenarioCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a what-if scenario linked to an emission report."""
    try:
        return await svc_create(
            db,
            company_id=user.company_id,
            name=body.name,
            description=body.description,
            base_report_id=body.base_report_id,
            parameters=body.parameters,
        )
    except ScenarioError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@router.get("/", response_model=PaginatedResponse[ScenarioOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def list_scenarios(
    request: Request,
    status: str | None = Query(default=None, pattern="^(draft|computed|archived)$"),
    sort_by: str = Query(default="created_at", pattern="^(created_at|updated_at|name)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List scenarios for the current user's company."""
    rows, total = await svc_list(
        db,
        company_id=user.company_id,
        status=status,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse[ScenarioOut](
        items=[ScenarioOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{scenario_id}", response_model=ScenarioOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_scenario(
    request: Request,
    scenario_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific scenario."""
    try:
        return await svc_get(db, scenario_id, user.company_id)
    except ScenarioError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@router.patch("/{scenario_id}", response_model=ScenarioOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def update_scenario(
    request: Request,
    scenario_id: str,
    body: ScenarioUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a scenario's name or description."""
    try:
        scenario = await svc_update(db, scenario_id, user.company_id, body.model_dump(exclude_unset=True))
    except ScenarioError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="update", resource_type="scenario", resource_id=scenario_id,
    )
    return scenario


@router.post("/{scenario_id}/compute", response_model=ScenarioOut)
@limiter.limit("5/minute")
async def compute_scenario(
    request: Request,
    scenario_id: str,
    user: User = Depends(require_credits("scenario_compute")),
    db: AsyncSession = Depends(get_db),
):
    """Run the what-if computation for a scenario."""
    try:
        scenario = await run_scenario(db, scenario_id, user.company_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Deduct credits only after computation succeeded
    from api.services.subscriptions import deduct_operation_credits
    await deduct_operation_credits(db, user.company_id, "scenario_compute")

    return scenario


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def delete_scenario(
    request: Request,
    scenario_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a scenario."""
    try:
        await svc_delete(db, scenario_id, user.company_id)
    except ScenarioError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="delete", resource_type="scenario", resource_id=scenario_id,
    )
