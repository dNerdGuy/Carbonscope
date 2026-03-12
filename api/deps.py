"""FastAPI dependencies — current user extraction, plan gates, DB sessions."""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import decode_access_token, is_token_revoked
from api.database import get_db
from api.models import User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from the Bearer token or httpOnly cookie."""
    token: str | None = None
    from_cookie = False

    if creds and creds.credentials:
        token = creds.credentials
    else:
        token = request.cookies.get("access_token")
        from_cookie = True

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # CSRF check when using cookie-based auth on state-changing methods
    if from_cookie and request.method not in ("GET", "HEAD", "OPTIONS"):
        csrf_cookie = request.cookies.get("csrf_token", "")
        csrf_header = request.headers.get("x-csrf-token", "")
        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed",
            )

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    # Check if token has been revoked (logout)
    jti = payload.get("jti")
    if jti and await is_token_revoked(db, jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    return user


def require_plan(feature: str) -> Callable:
    """Dependency factory that gates an endpoint behind a plan feature.

    Usage: Depends(require_plan("pdf_export"))
    """

    async def _check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        from api.services.subscriptions import check_feature_access

        if not await check_feature_access(db, user.company_id, feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature}' requires a Pro or Enterprise plan. Upgrade at /billing/subscription",
            )
        return user

    return _check


def require_credits(operation: str) -> Callable:
    """Dependency factory that checks and deducts credits for an operation.

    Usage: Depends(require_credits("estimate"))
    """

    async def _check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        from api.services.subscriptions import check_credit_and_deduct

        try:
            await check_credit_and_deduct(db, user.company_id, operation)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=str(e),
            )
        return user

    return _check


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Dependency that ensures the current user has admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
