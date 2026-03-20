"""Team management routes — invitations, member listing, role updates."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import hash_password
from api.config import RATE_LIMIT_DEFAULT
from api.database import get_db
from api.deps import get_current_user, require_admin
from api.limiter import limiter
from api.models import Company, Invitation, User, UserRole, _utcnow
from api.schemas import InviteAccept, InviteCreate, InviteOut, PaginatedResponse, TeamMemberOut, Token, UserOut
from api.services import audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/team", tags=["team"])

INVITE_EXPIRE_DAYS = 7


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/invite", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def invite_member(
    request: Request,
    body: InviteCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Invite a new member to the current company (admin only)."""
    # Check if email is already a member of this company
    existing = (
        await db.execute(
            select(User).where(User.email == body.email, User.company_id == user.company_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member of this company")

    # Check for pending invite
    pending = (
        await db.execute(
            select(Invitation).where(
                Invitation.email == body.email,
                Invitation.company_id == user.company_id,
                Invitation.accepted_at.is_(None),
                Invitation.expires_at > _utcnow(),
            )
        )
    ).scalar_one_or_none()
    if pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A pending invitation already exists for this email")

    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        company_id=user.company_id,
        email=body.email,
        role=body.role,
        invited_by=user.id,
        token_hash=_hash_token(token),
        expires_at=_utcnow() + timedelta(days=INVITE_EXPIRE_DAYS),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="invite", resource_type="team_member", resource_id=invitation.id,
        detail=f"Invited {body.email} as {body.role}",
    )

    logger.info("Team invite created: company=%s email=%s", user.company_id, body.email)
    # In production, you would send an email here with the invite token.
    # For now, the token is not exposed in the response (only the hash is stored).
    return invitation


@router.post("/invite/accept", response_model=UserOut)
@limiter.limit("5/minute")
async def accept_invite(
    request: Request,
    body: InviteAccept,
    db: AsyncSession = Depends(get_db),
):
    """Accept a team invitation and create a user account."""
    token_hash = _hash_token(body.token)
    invitation = (
        await db.execute(
            select(Invitation).where(
                Invitation.token_hash == token_hash,
                Invitation.accepted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired invitation")

    if invitation.expires_at < _utcnow():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invitation has expired")

    # Check email not already registered
    existing = (
        await db.execute(select(User).where(User.email == invitation.email, User.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")

    new_user = User(
        email=invitation.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        company_id=invitation.company_id,
        role=invitation.role,
        is_active=True,
    )
    db.add(new_user)
    invitation.accepted_at = _utcnow()
    await db.commit()
    await db.refresh(new_user)

    await audit.record(
        db, user_id=new_user.id, company_id=invitation.company_id,
        action="accept_invite", resource_type="team_member", resource_id=new_user.id,
    )

    return new_user


@router.get("/members", response_model=PaginatedResponse[TeamMemberOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def list_members(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all members of the current company."""
    base = select(User).where(User.company_id == user.company_id, User.deleted_at.is_(None))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        await db.execute(base.order_by(User.created_at).limit(limit).offset(offset))
    ).scalars().all()
    return PaginatedResponse(items=rows, total=total, limit=limit, offset=offset)


@router.get("/invitations", response_model=PaginatedResponse[InviteOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def list_invitations(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List pending invitations for the current company (admin only)."""
    base = select(Invitation).where(
        Invitation.company_id == user.company_id,
        Invitation.accepted_at.is_(None),
        Invitation.expires_at > _utcnow(),
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        await db.execute(base.order_by(Invitation.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return PaginatedResponse(items=rows, total=total, limit=limit, offset=offset)


@router.patch("/members/{member_id}/role", response_model=TeamMemberOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def update_member_role(
    request: Request,
    member_id: str,
    role: str = Query(pattern="^(admin|member)$"),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a team member's role (admin only)."""
    if member_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role")

    target = (
        await db.execute(
            select(User).where(
                User.id == member_id,
                User.company_id == user.company_id,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    target.role = role
    await db.commit()
    await db.refresh(target)

    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="update_role", resource_type="team_member", resource_id=member_id,
        detail=f"Role changed to {role}",
    )

    return target


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def remove_member(
    request: Request,
    member_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Remove a team member from the company (admin only)."""
    if member_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove yourself")

    target = (
        await db.execute(
            select(User).where(
                User.id == member_id,
                User.company_id == user.company_id,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    target.is_active = False
    target.deleted_at = _utcnow()
    target.email = f"removed_{target.id}_{secrets.token_hex(4)}@removed.local"
    target.full_name = "Removed User"
    await db.commit()

    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="remove", resource_type="team_member", resource_id=member_id,
    )
