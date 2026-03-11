"""Company & data upload routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.models import Company, DataUpload, User, _utcnow
from api.schemas import (
    CompanyOut,
    CompanyUpdate,
    DataUploadCreate,
    DataUploadOut,
    DataUploadUpdate,
    PaginatedResponse,
)

router = APIRouter(tags=["company"])


# ── Company profile ─────────────────────────────────────────────────


@router.get("/company", response_model=CompanyOut)
async def get_company(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's company profile."""
    result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.patch("/company", response_model=CompanyOut)
async def update_company(
    body: CompanyUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update company profile fields."""
    result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(company, key, value)

    await db.commit()
    await db.refresh(company)
    return company


# ── Data uploads ────────────────────────────────────────────────────


@router.post("/data", response_model=DataUploadOut, status_code=status.HTTP_201_CREATED)
async def upload_data(
    body: DataUploadCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload operational data for a given reporting year."""
    upload = DataUpload(
        company_id=user.company_id,
        year=body.year,
        provided_data=body.provided_data,
        notes=body.notes,
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)
    return upload


@router.get("/data", response_model=PaginatedResponse[DataUploadOut])
async def list_data_uploads(
    year: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List data uploads with pagination and optional year filter."""
    base = select(DataUpload).where(
        DataUpload.company_id == user.company_id,
        DataUpload.deleted_at.is_(None),
    )
    if year is not None:
        base = base.where(DataUpload.year == year)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    result = await db.execute(
        base.order_by(DataUpload.year.desc()).limit(limit).offset(offset)
    )
    return PaginatedResponse(items=result.scalars().all(), total=total, limit=limit, offset=offset)


@router.get("/data/{upload_id}", response_model=DataUploadOut)
async def get_data_upload(
    upload_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific data upload."""
    result = await db.execute(
        select(DataUpload).where(
            DataUpload.id == upload_id,
            DataUpload.company_id == user.company_id,
            DataUpload.deleted_at.is_(None),
        )
    )
    upload = result.scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data upload not found")
    return upload


@router.patch("/data/{upload_id}", response_model=DataUploadOut)
async def update_data_upload(
    upload_id: str,
    body: DataUploadUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a data upload's fields."""
    result = await db.execute(
        select(DataUpload).where(
            DataUpload.id == upload_id,
            DataUpload.company_id == user.company_id,
            DataUpload.deleted_at.is_(None),
        )
    )
    upload = result.scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data upload not found")

    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(upload, key, value)

    await db.commit()
    await db.refresh(upload)
    return upload


@router.delete("/data/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_upload(
    upload_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a data upload."""
    result = await db.execute(
        select(DataUpload).where(
            DataUpload.id == upload_id,
            DataUpload.company_id == user.company_id,
            DataUpload.deleted_at.is_(None),
        )
    )
    upload = result.scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data upload not found")

    upload.deleted_at = _utcnow()
    await db.commit()
