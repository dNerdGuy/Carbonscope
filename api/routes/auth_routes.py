"""Auth routes — registration, login, logout, refresh tokens, password reset."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_access_token,
    hash_password,
    is_token_revoked,
    revoke_access_token,
    revoke_refresh_tokens,
    validate_refresh_token,
    validate_reset_token,
    verify_password,
)
from api.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    COOKIE_DOMAIN,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    RATE_LIMIT_AUTH,
)
from api.database import get_db
from api.deps import get_current_user
from api.limiter import limiter
from api.models import Company, User
from api.schemas import PasswordChange, Token, UserLogin, UserOut, UserProfileUpdate, UserRegister
from api.services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenWithRefresh(BaseModel):
    access_token: str
    refresh_token: str
    csrf_token: str | None = None
    token_type: str = "bearer"


def _set_auth_cookies(response: Response, access_token: str, csrf_token: str) -> None:
    """Set httpOnly access token cookie and readable CSRF cookie."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


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


@router.post("/login", response_model=TokenWithRefresh)
@limiter.limit(RATE_LIMIT_AUTH)
async def login(request: Request, body: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate and return JWT access + refresh tokens."""
    # Look up user first for brute force protection
    result = await db.execute(select(User).where(User.email == body.email))
    user_row = result.scalar_one_or_none()

    if user_row is not None:
        # Check account lockout (handle SQLite naive datetimes)
        if user_row.locked_until:
            lock_dt = user_row.locked_until if user_row.locked_until.tzinfo else user_row.locked_until.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < lock_dt:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Account temporarily locked due to too many failed attempts. Try again later.",
                )

    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        # Increment failed attempts if user exists
        if user_row is not None:
            user_row.failed_login_attempts = (user_row.failed_login_attempts or 0) + 1
            if user_row.failed_login_attempts >= 5:
                from datetime import timedelta
                user_row.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Reset failed attempts on success
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)

    access = create_access_token(user.id, user.company_id)
    refresh = await create_refresh_token(db, user.id, user.company_id)
    csrf = secrets.token_hex(32)
    await db.commit()

    response = Response(
        content=TokenWithRefresh(
            access_token=access, refresh_token=refresh, csrf_token=csrf,
        ).model_dump_json(),
        media_type="application/json",
    )
    _set_auth_cookies(response, access, csrf)
    return response


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
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="change_password", resource_type="user", resource_id=user.id,
    )
    await db.commit()


@router.post("/refresh", response_model=TokenWithRefresh)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new access + refresh token pair (rotation)."""
    data = await validate_refresh_token(db, body.refresh_token)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    access = create_access_token(data["user_id"], data["company_id"])
    refresh = await create_refresh_token(db, data["user_id"], data["company_id"])
    csrf = secrets.token_hex(32)
    await db.commit()

    response = Response(
        content=TokenWithRefresh(
            access_token=access, refresh_token=refresh, csrf_token=csrf,
        ).model_dump_json(),
        media_type="application/json",
    )
    _set_auth_cookies(response, access, csrf)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the current access token and all refresh tokens for the user."""
    # Extract the current token's jti and exp for revocation
    from fastapi.security import HTTPAuthorizationCredentials
    auth_header = request.headers.get("authorization", "")
    token_str = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    if not token_str:
        token_str = request.cookies.get("access_token", "")
    if token_str:
        try:
            payload = decode_access_token(token_str)
            jti = payload.get("jti")
            exp_ts = payload.get("exp")
            if jti and exp_ts:
                expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
                await revoke_access_token(db, jti, user.id, expires_at)
        except Exception:
            pass  # Token already invalid, still revoke refresh tokens

    await revoke_refresh_tokens(db, user.id)
    await db.commit()

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie("access_token", path="/", domain=COOKIE_DOMAIN)
    response.delete_cookie("csrf_token", path="/", domain=COOKIE_DOMAIN)
    return response


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_AUTH)
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset. Sends a reset token via email."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is not None:
        token = create_reset_token(user.id, user.email)
        from api.services.email_async import send_password_reset_email
        await send_password_reset_email(user.email, token)
    # Always return 204 to prevent email enumeration


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_AUTH)
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a valid reset token."""
    data = validate_reset_token(body.token)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    result = await db.execute(select(User).where(User.id == data["user_id"]))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.hashed_password = hash_password(body.new_password)
    await db.commit()
