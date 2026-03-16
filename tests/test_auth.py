import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.person import Person, AccountState
from app.models.auth import UserSession, Invite, MagicLinkToken
from app.services.auth_service import (
    create_session,
    validate_session,
    delete_session,
    create_invite,
    claim_invite,
    create_magic_link,
    validate_magic_link,
    _hash_token,
)


@pytest.mark.asyncio
async def test_create_and_validate_session(seeded_db: AsyncSession):
    token = await create_session(
        seeded_db,
        person_id="tyler-000-0000-0000-000000000002",
        auth_method="magic_link",
    )
    await seeded_db.commit()

    person = await validate_session(seeded_db, token)
    assert person is not None
    assert person.first_name == "Tyler"


@pytest.mark.asyncio
async def test_invalid_session_returns_none(seeded_db: AsyncSession):
    person = await validate_session(seeded_db, "bogus-token")
    assert person is None


@pytest.mark.asyncio
async def test_delete_session(seeded_db: AsyncSession):
    token = await create_session(
        seeded_db,
        person_id="tyler-000-0000-0000-000000000002",
        auth_method="magic_link",
    )
    await seeded_db.commit()

    await delete_session(seeded_db, token)
    await seeded_db.commit()

    person = await validate_session(seeded_db, token)
    assert person is None


@pytest.mark.asyncio
async def test_expired_session_rejected(seeded_db: AsyncSession):
    token = await create_session(
        seeded_db,
        person_id="tyler-000-0000-0000-000000000002",
        auth_method="magic_link",
    )
    await seeded_db.commit()

    # Manually expire the session
    token_hash = _hash_token(token)
    result = await seeded_db.execute(
        select(UserSession).where(UserSession.token_hash == token_hash)
    )
    session = result.scalar_one()
    session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await seeded_db.commit()

    person = await validate_session(seeded_db, token)
    assert person is None


@pytest.mark.asyncio
async def test_suspended_user_session_rejected(seeded_db: AsyncSession):
    # Suspend Tyler
    result = await seeded_db.execute(
        select(Person).where(Person.id == "tyler-000-0000-0000-000000000002")
    )
    tyler = result.scalar_one()
    tyler.account_state = AccountState.suspended.value
    await seeded_db.commit()

    token = await create_session(
        seeded_db,
        person_id="tyler-000-0000-0000-000000000002",
        auth_method="magic_link",
    )
    await seeded_db.commit()

    person = await validate_session(seeded_db, token)
    assert person is None


@pytest.mark.asyncio
async def test_invite_create_and_claim(seeded_db: AsyncSession):
    invite = await create_invite(
        seeded_db,
        person_id="member-00-0000-0000-000000000005",
        created_by="tyler-000-0000-0000-000000000002",
    )
    await seeded_db.commit()

    assert invite.token is not None
    assert invite.claimed_at is None

    person = await claim_invite(seeded_db, invite.token)
    assert person is not None
    assert person.first_name == "Jane"

    # Can't claim twice
    person2 = await claim_invite(seeded_db, invite.token)
    assert person2 is None


@pytest.mark.asyncio
async def test_expired_invite_rejected(seeded_db: AsyncSession):
    invite = await create_invite(
        seeded_db,
        person_id="member-00-0000-0000-000000000005",
        created_by="tyler-000-0000-0000-000000000002",
    )
    invite.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await seeded_db.commit()

    person = await claim_invite(seeded_db, invite.token)
    assert person is None


@pytest.mark.asyncio
async def test_magic_link_create_and_validate(seeded_db: AsyncSession):
    token = await create_magic_link(seeded_db, "tyler-000-0000-0000-000000000002")
    await seeded_db.commit()

    person = await validate_magic_link(seeded_db, token)
    assert person is not None
    assert person.first_name == "Tyler"

    # Can't use twice
    person2 = await validate_magic_link(seeded_db, token)
    assert person2 is None


@pytest.mark.asyncio
async def test_expired_magic_link_rejected(seeded_db: AsyncSession):
    token = await create_magic_link(seeded_db, "tyler-000-0000-0000-000000000002")
    await seeded_db.commit()

    # Expire the token
    token_hash = _hash_token(token)
    result = await seeded_db.execute(
        select(MagicLinkToken).where(MagicLinkToken.token_hash == token_hash)
    )
    ml = result.scalar_one()
    ml.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await seeded_db.commit()

    person = await validate_magic_link(seeded_db, token)
    assert person is None
