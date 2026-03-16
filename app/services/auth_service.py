import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import UserSession, Invite, MagicLinkToken
from app.models.person import Person, AccountState

SESSION_TOKEN_BYTES = 32
SESSION_EXPIRY_DAYS = 30
MAX_SESSIONS_PER_PERSON = 10
MAGIC_LINK_EXPIRY_MINUTES = 15
INVITE_EXPIRY_DAYS = 30


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_session_token() -> str:
    return secrets.token_hex(SESSION_TOKEN_BYTES)


def generate_invite_token() -> str:
    return secrets.token_hex(32)


def generate_magic_link_token() -> str:
    return secrets.token_hex(32)


async def create_session(
    db: AsyncSession,
    person_id: str,
    auth_method: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Create a new session, returning the raw token (to be set as cookie)."""
    token = generate_session_token()
    token_hash = _hash_token(token)

    # Enforce max sessions per person — evict oldest
    result = await db.execute(
        select(UserSession)
        .where(UserSession.person_id == person_id)
        .order_by(UserSession.created_at.desc())
    )
    existing = result.scalars().all()
    if len(existing) >= MAX_SESSIONS_PER_PERSON:
        for old_session in existing[MAX_SESSIONS_PER_PERSON - 1:]:
            await db.delete(old_session)

    session = UserSession(
        person_id=person_id,
        token_hash=token_hash,
        auth_method=auth_method,
        expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(session)
    await db.flush()
    return token


async def validate_session(db: AsyncSession, token: str) -> Person | None:
    """Validate a session token, return the Person or None."""
    token_hash = _hash_token(token)
    result = await db.execute(
        select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None

    # Sliding expiry
    session.last_used = datetime.now(timezone.utc)
    session.expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS)

    result = await db.execute(
        select(Person).where(
            Person.id == session.person_id,
            Person.account_state == AccountState.active.value,
        )
    )
    return result.scalar_one_or_none()


async def delete_session(db: AsyncSession, token: str) -> None:
    token_hash = _hash_token(token)
    await db.execute(
        delete(UserSession).where(UserSession.token_hash == token_hash)
    )


async def create_invite(
    db: AsyncSession,
    person_id: str,
    created_by: str,
) -> Invite:
    """Create an invite for a person. Returns the Invite with raw token."""
    token = generate_invite_token()
    invite = Invite(
        person_id=person_id,
        token=token,
        created_by=created_by,
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRY_DAYS),
    )
    db.add(invite)
    await db.flush()
    return invite


async def claim_invite(db: AsyncSession, token: str) -> Person | None:
    """Claim an invite token. Returns the Person if valid, None otherwise."""
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
        return None

    invite.claimed_at = datetime.now(timezone.utc)

    result = await db.execute(select(Person).where(Person.id == invite.person_id))
    person = result.scalar_one_or_none()
    if person:
        person.account_state = AccountState.active.value
    return person


async def create_magic_link(db: AsyncSession, person_id: str) -> str:
    """Create a magic link token. Returns the raw token."""
    token = generate_magic_link_token()
    token_hash = _hash_token(token)
    ml = MagicLinkToken(
        person_id=person_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRY_MINUTES),
    )
    db.add(ml)
    await db.flush()
    return token


async def validate_magic_link(db: AsyncSession, token: str) -> Person | None:
    """Validate and consume a magic link token. Returns Person if valid."""
    token_hash = _hash_token(token)
    result = await db.execute(
        select(MagicLinkToken).where(
            MagicLinkToken.token_hash == token_hash,
            MagicLinkToken.used_at.is_(None),
            MagicLinkToken.expires_at > datetime.now(timezone.utc),
        )
    )
    ml = result.scalar_one_or_none()
    if not ml:
        return None

    ml.used_at = datetime.now(timezone.utc)

    result = await db.execute(select(Person).where(Person.id == ml.person_id))
    return result.scalar_one_or_none()
