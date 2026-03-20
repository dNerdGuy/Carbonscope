"""MFA (Multi-Factor Authentication) routes — TOTP setup, verify, disable."""

from __future__ import annotations

import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import create_access_token, create_refresh_token
from api.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    COOKIE_DOMAIN,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    RATE_LIMIT_AUTH,
    RATE_LIMIT_MFA_VALIDATE,
)
from api.database import get_db
from api.deps import get_current_user, get_mfa_pending_user
from api.limiter import limiter
from api.models import MFASecret, User
from api.schemas import MFASetupOut, MFAStatusOut, MFAVerifyRequest
from api.services.mfa import (
    build_provisioning_uri,
    decrypt_secret,
    encrypt_secret,
    generate_backup_codes,
    generate_totp_secret,
    hash_backup_code,
    verify_totp,
)
from api.services import audit

router = APIRouter(prefix="/auth/mfa", tags=["mfa"])


class MFAValidateResponse(BaseModel):
    access_token: str
    refresh_token: str
    csrf_token: str | None = None
    token_type: str = "bearer"
    mfa_verified: bool = True


@router.get("/status", response_model=MFAStatusOut)
@limiter.limit(RATE_LIMIT_AUTH)
async def mfa_status(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check whether MFA is enabled for the current user."""
    result = await db.execute(
        select(MFASecret).where(MFASecret.user_id == user.id)
    )
    secret_row = result.scalar_one_or_none()
    return {"mfa_enabled": secret_row is not None and secret_row.is_enabled}


@router.post("/setup", response_model=MFASetupOut)
@limiter.limit(RATE_LIMIT_AUTH)
async def setup_mfa(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate TOTP secret and backup codes. MFA is not active until /verify is called."""
    # Check if already enabled
    result = await db.execute(
        select(MFASecret).where(MFASecret.user_id == user.id)
    )
    existing = result.scalar_one_or_none()
    if existing and existing.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MFA is already enabled. Disable it first to reconfigure.",
        )

    secret = generate_totp_secret()
    backup_codes = generate_backup_codes()
    hashed_codes = json.dumps([hash_backup_code(c) for c in backup_codes])
    uri = build_provisioning_uri(secret, user.email)
    encrypted = encrypt_secret(secret)

    if existing:
        # Overwrite pending (not-yet-enabled) setup
        existing.totp_secret = encrypted
        existing.backup_codes = hashed_codes
        existing.is_enabled = False
    else:
        db.add(MFASecret(
            user_id=user.id,
            totp_secret=encrypted,
            backup_codes=hashed_codes,
            is_enabled=False,
        ))

    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="mfa_setup", resource_type="mfa", resource_id=str(user.id),
    )
    await db.commit()

    return {
        "secret": secret,
        "provisioning_uri": uri,
        "backup_codes": backup_codes,
    }


@router.post("/verify", response_model=MFAStatusOut)
@limiter.limit(RATE_LIMIT_AUTH)
async def verify_and_enable_mfa(
    request: Request,
    body: MFAVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify a TOTP code to activate MFA. Must call /setup first."""
    result = await db.execute(
        select(MFASecret).where(MFASecret.user_id == user.id)
    )
    secret_row = result.scalar_one_or_none()
    if not secret_row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Call /setup first")

    if not verify_totp(decrypt_secret(secret_row.totp_secret), body.totp_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid TOTP code")

    secret_row.is_enabled = True
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="mfa_enabled", resource_type="mfa", resource_id=str(user.id),
    )
    await db.commit()
    return {"mfa_enabled": True}


@router.post("/validate", response_model=MFAValidateResponse)
@limiter.limit(RATE_LIMIT_MFA_VALIDATE)
async def validate_totp(
    request: Request,
    body: MFAVerifyRequest,
    user: User = Depends(get_mfa_pending_user),
    db: AsyncSession = Depends(get_db),
):
    """Complete the MFA login step: validate TOTP code and issue full tokens.

    Requires an ``mfa_pending`` token (returned by ``POST /auth/login`` when MFA
    is enabled) in the Authorization header.
    """
    result = await db.execute(
        select(MFASecret).where(MFASecret.user_id == user.id, MFASecret.is_enabled.is_(True))
    )
    secret_row = result.scalar_one_or_none()
    if not secret_row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA is not enabled")

    if not verify_totp(decrypt_secret(secret_row.totp_secret), body.totp_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid TOTP code")

    # TOTP verified — issue full access + refresh tokens
    access = create_access_token(user.id, user.company_id)
    refresh = await create_refresh_token(db, user.id, user.company_id)
    csrf = secrets.token_hex(32)

    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="login_mfa_verified", resource_type="user", resource_id=user.id,
    )
    await db.commit()

    response = Response(
        content=MFAValidateResponse(
            access_token=access, refresh_token=refresh, csrf_token=csrf,
        ).model_dump_json(),
        media_type="application/json",
    )
    from api.routes.auth_routes import _set_auth_cookies
    _set_auth_cookies(response, access, csrf, refresh_token=refresh)
    return response


@router.delete("/disable", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_AUTH)
async def disable_mfa(
    request: Request,
    body: MFAVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable MFA — requires a valid TOTP code for confirmation."""
    result = await db.execute(
        select(MFASecret).where(MFASecret.user_id == user.id, MFASecret.is_enabled.is_(True))
    )
    secret_row = result.scalar_one_or_none()
    if not secret_row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA is not enabled")

    if not verify_totp(decrypt_secret(secret_row.totp_secret), body.totp_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid TOTP code")

    await db.delete(secret_row)
    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="mfa_disabled", resource_type="mfa", resource_id=str(user.id),
    )
    await db.commit()
