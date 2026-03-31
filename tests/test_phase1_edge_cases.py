import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import MagicLinkToken, UserSession
from app.models.person import AccountState, Person, Visibility
from app.models.relationships import ParentChild
from app.services.auth_service import (
    _hash_token,
    create_magic_link,
    create_session,
    validate_session,
)

ROOT_ID = "root-0000-0000-0000-000000000001"
ADMIN_ID = "alex-000-0000-0000-000000000002"
ADMIN2_ID = "maria-00-0000-0000-000000000003"
MEMBER_ID = "member-00-0000-0000-000000000005"


@pytest.mark.asyncio
async def test_create_person_accepts_unicode_names(admin_client: AsyncClient):
    resp = await admin_client.post(
        "/api/persons",
        json={"first_name": "Анна", "last_name": "Семёнова"},
    )
    assert resp.status_code == 201
    assert resp.json()["display_name"] == "Анна Семёнова"


@pytest.mark.asyncio
async def test_create_person_rejects_very_long_first_name(admin_client: AsyncClient):
    resp = await admin_client.post(
        "/api/persons",
        json={"first_name": "A" * 201, "last_name": "Rivera"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_sql_injection_payload_does_not_bypass_filters(admin_client: AsyncClient):
    resp = await admin_client.get("/api/persons", params={"search": "Alex' OR 1=1 --"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_branch_filter_sql_injection_payload_does_not_match(admin_client: AsyncClient):
    resp = await admin_client.get("/api/persons", params={"branch": "martin' OR 1=1 --"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_expired_magic_link_route_rejected(client: AsyncClient, seeded_db: AsyncSession):
    token = await create_magic_link(seeded_db, ADMIN_ID)
    await seeded_db.commit()

    result = await seeded_db.execute(
        select(MagicLinkToken).where(MagicLinkToken.token_hash == _hash_token(token))
    )
    magic_link = result.scalar_one()
    magic_link.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await seeded_db.commit()

    resp = await client.get(f"/auth/magic-link/{token}")
    assert resp.status_code == 404
    assert "set-cookie" not in resp.headers


@pytest.mark.asyncio
async def test_magic_link_route_cannot_be_reused(client: AsyncClient, seeded_db: AsyncSession):
    token = await create_magic_link(seeded_db, ADMIN_ID)
    await seeded_db.commit()

    first = await client.get(f"/auth/magic-link/{token}")
    second = await client.get(f"/auth/magic-link/{token}")

    assert first.status_code == 200
    assert second.status_code == 404


@pytest.mark.asyncio
async def test_session_limit_evicts_oldest_session(seeded_db: AsyncSession):
    tokens: list[str] = []
    for _ in range(11):
        tokens.append(await create_session(seeded_db, ADMIN_ID, "magic_link"))
        await seeded_db.commit()

    result = await seeded_db.execute(
        select(UserSession)
        .where(UserSession.person_id == ADMIN_ID)
        .order_by(UserSession.created_at.asc())
    )
    sessions = result.scalars().all()

    assert len(sessions) == 10
    assert await validate_session(seeded_db, tokens[0]) is None
    assert await validate_session(seeded_db, tokens[-1]) is not None


@pytest.mark.asyncio
async def test_root_person_redacted_in_list_detail_tree_and_search(
    admin_client: AsyncClient,
    seeded_db: AsyncSession,
):
    root = await seeded_db.get(Person, ROOT_ID)
    root.first_name = "Mia"
    root.last_name = "Rivera"
    root.nickname = "Moon"
    await seeded_db.commit()

    list_resp = await admin_client.get("/api/persons")
    detail_resp = await admin_client.get(f"/api/persons/{ROOT_ID}")
    tree_resp = await admin_client.get("/api/tree")
    search_resp = await admin_client.get("/api/persons", params={"search": "Mia"})

    assert list_resp.status_code == 200
    assert detail_resp.status_code == 200
    assert tree_resp.status_code == 200
    assert search_resp.status_code == 200

    list_root = next(person for person in list_resp.json() if person["id"] == ROOT_ID)
    tree_root = next(person for person in tree_resp.json()["persons"] if person["id"] == ROOT_ID)
    detail_root = detail_resp.json()

    for root_summary in (list_root, tree_root):
        assert root_summary["display_name"] == "Семья Володиных"
        assert root_summary["nickname"] is None

    assert detail_root["display_name"] == "Семья Володиных"
    assert detail_root["first_name"] is None
    assert detail_root["last_name"] is None
    assert detail_root["nickname"] is None
    assert search_resp.json() == []


@pytest.mark.asyncio
async def test_concurrent_requests_to_same_endpoint_return_consistent_results(
    admin_client: AsyncClient,
):
    responses = await asyncio.gather(*[admin_client.get("/api/persons") for _ in range(5)])

    assert all(resp.status_code == 200 for resp in responses)
    person_id_sets = [{person["id"] for person in resp.json()} for resp in responses]
    assert all(person_ids == person_id_sets[0] for person_ids in person_id_sets[1:])


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Phase 1 accepts blank names because the schema only enforces max_length.",
    strict=True,
)
async def test_create_person_rejects_empty_names(admin_client: AsyncClient):
    resp = await admin_client.post(
        "/api/persons",
        json={"first_name": "", "last_name": ""},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_parent_child_rejects_circular_relationship(admin_client: AsyncClient):
    resp = await admin_client.post(
        "/api/relationships/parent-child",
        json={"parent_id": ROOT_ID, "child_id": ADMIN_ID, "kind": "biological"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_duplicate_partnership_with_null_start_date_is_rejected(admin_client: AsyncClient):
    resp = await admin_client.post(
        "/api/relationships/partnership",
        json={"person_a_id": ADMIN_ID, "person_b_id": ADMIN2_ID, "kind": "married"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_root_real_name_is_not_searchable(
    admin_client: AsyncClient,
    seeded_db: AsyncSession,
):
    root = await seeded_db.get(Person, ROOT_ID)
    root.first_name = "Mia"
    root.last_name = "Rivera"
    await seeded_db.commit()

    resp = await admin_client.get("/api/persons", params={"search": "Mia"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_tree_omits_hidden_person_relationships(
    member_client: AsyncClient,
    seeded_db: AsyncSession,
):
    hidden_person = Person(
        id="hidden-00-0000-0000-000000000099",
        first_name="Hidden",
        last_name="Person",
        visibility=Visibility.hidden.value,
        account_state=AccountState.active.value,
    )
    seeded_db.add(hidden_person)
    await seeded_db.flush()
    seeded_db.add(ParentChild(parent_id=hidden_person.id, child_id=MEMBER_ID, kind="biological"))
    await seeded_db.commit()

    resp = await member_client.get("/api/tree")
    assert resp.status_code == 200
    leaked_ids = {
        relation["parent_id"]
        for relation in resp.json()["parent_child"]
    } | {
        relation["child_id"]
        for relation in resp.json()["parent_child"]
    }
    assert hidden_person.id not in leaked_ids


@pytest.mark.asyncio
async def test_suspended_user_magic_link_login_is_rejected(
    client: AsyncClient,
    seeded_db: AsyncSession,
):
    suspended = Person(
        id="suspd-0000-0000-0000-000000000010",
        first_name="Suspended",
        last_name="User",
        contact_email="suspended@example.com",
        account_state=AccountState.suspended.value,
    )
    seeded_db.add(suspended)
    await seeded_db.commit()

    token = await create_magic_link(seeded_db, suspended.id)
    await seeded_db.commit()

    resp = await client.get(f"/auth/magic-link/{token}")
    assert resp.status_code == 404
    assert "set-cookie" not in resp.headers
