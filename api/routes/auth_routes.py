"""Auth routes — registration and login."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import authenticate_user, create_access_token, hash_password, verify_password
from api.config import RATE_LIMIT_AUTH
from api.database import get_db
from api.deps import get_current_user
from api.limiter import limiter
from api.models import Company, User
from api.schemas import PasswordChange, Token, UserLogin, UserOut, UserProfileUpdate, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_AUTH)
async def register(request: Request, body: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user and company."""
    # Check for existing email
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    company = Company(
        name=body.company_name,
        industry=body.industry,
        region=body.region,
    )
    db.add(company)
    await db.flush()  # get company.id

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        company_id=company.id,
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
@limiter.limit(RATE_LIMIT_AUTH)
async def login(request: Request, body: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate and return a JWT."""
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(user.id, user.company_id)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
async def get_profile(user: User = Depends(get_current_user)):
    """Get the current user's profile."""
    return user


@router.patch("/me", response_model=UserOut)
async def update_profile(
    body: UserProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile (name, email)."""
    updates = body.model_dump(exclude_unset=True)

    if "email" in updates and updates["email"] != user.email:
        existing = await db.execute(select(User).where(User.email == updates["email"]))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    for key, value in updates.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: PasswordChange,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    user.hashed_password = hash_password(body.new_password)
    await db.commit()
