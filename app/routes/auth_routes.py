from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import SESSION_COOKIE_NAME, get_current_user, require_auth
from app.config import get_settings
from app.database import get_db
from app.models.person import Person
from app.services.auth_service import (
    claim_invite,
    create_magic_link,
    create_session,
    delete_session,
    validate_magic_link,
)

router = APIRouter(tags=["auth"])


class MagicLinkRequest(BaseModel):
    email: str


@router.get("/invite/{token}")
async def get_invite(token: str, db: AsyncSession = Depends(get_db)):
    """Show invite claim page data."""
    from app.models.auth import Invite
    from datetime import datetime, timezone

    result = await db.execute(
        select(Invite).where(
            Invite.token == token,
            Invite.claimed_at.is_(None),
            Invite.revoked == False,
            Invite.expires_at > datetime.now(timezone.utc),
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite")

    result = await db.execute(select(Person).where(Person.id == invite.person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    return {
        "person_name": person.display_name,
        "branch": person.branch,
        "token": token,
    }


@router.post("/invite/{token}/claim")
async def claim_invite_route(
    token: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Claim an invite and create a session."""
    person = await claim_invite(db, token)
    if not person:
        raise HTTPException(status_code=404, detail="Invalid or expired invite")

    session_token = await create_session(
        db,
        person_id=person.id,
        auth_method="invite_code",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    settings = get_settings()
    is_secure = settings.BASE_URL.startswith("https")
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=30 * 24 * 3600,
        path="/",
    )
    return {"status": "ok", "person_id": person.id}


@router.post("/auth/magic-link")
async def request_magic_link(
    body: MagicLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a magic link. Always returns 200 to prevent email enumeration."""
    result = await db.execute(
        select(Person).where(Person.contact_email == body.email.lower().strip())
    )
    person = result.scalar_one_or_none()

    if person:
        token = await create_magic_link(db, person.id)
        settings = get_settings()
        link = f"{settings.BASE_URL}/auth/magic-link/{token}"
        # TODO: Send email via SMTP or Envelope API
        # For now, log the link (dev only)
        import logging
        logging.getLogger(__name__).info(f"Magic link for {person.contact_email}: {link}")

    return {"message": "If that email is registered, a login link has been sent."}


@router.get("/auth/magic-link/{token}")
async def verify_magic_link(
    token: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Verify a magic link token and create a session."""
    person = await validate_magic_link(db, token)
    if not person:
        raise HTTPException(status_code=404, detail="Invalid or expired magic link")

    session_token = await create_session(
        db,
        person_id=person.id,
        auth_method="magic_link",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    settings = get_settings()
    is_secure = settings.BASE_URL.startswith("https")
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=30 * 24 * 3600,
        path="/",
    )
    return {"status": "ok", "person_id": person.id}


@router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        await delete_session(db, token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"status": "ok"}


@router.get("/auth/me")
async def get_me(current_user: Person = Depends(require_auth)):
    return {
        "id": current_user.id,
        "display_name": current_user.display_name,
        "is_admin": current_user.is_admin,
        "branch": current_user.branch,
    }
