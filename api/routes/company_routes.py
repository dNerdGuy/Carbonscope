"""Company & data upload routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.models import Company, DataUpload, User
from api.schemas import CompanyOut, CompanyUpdate, DataUploadCreate, DataUploadOut

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


@router.get("/data", response_model=list[DataUploadOut])
async def list_data_uploads(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all data uploads for the current company."""
    result = await db.execute(
        select(DataUpload)
        .where(DataUpload.company_id == user.company_id)
        .order_by(DataUpload.year.desc())
    )
    return result.scalars().all()


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
        )
    )
    upload = result.scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data upload not found")
    return upload
