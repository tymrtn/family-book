import json
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.auth import Invite
from app.models.media import Media
from app.models.moments import Moment, MomentComment, MomentReaction
from app.models.person import Person
from app.models.relationships import ParentChild, Partnership
from app.config import get_settings
from app.services.auth_service import create_session
from app.services.site_settings import claim_site, get_site_settings


def _seed_records() -> dict:
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "family_tree.json").read_text())
    parent_child = data["parent_child"][0]
    partnership = data["partnerships"][0]
    moment = data["moments"][0]
    comment = data["moment_comments"][0]
    reaction = data["moment_reactions"][0]

    person_ids = {
        parent_child["parent_id"],
        parent_child["child_id"],
        partnership["person_a_id"],
        partnership["person_b_id"],
        moment["person_id"],
        comment["person_id"],
        reaction["person_id"],
    }
    persons = [person for person in data["persons"] if person["id"] in person_ids]
    return {
        "persons": persons,
        "parent_child": parent_child,
        "partnership": partnership,
        "moment": moment,
        "comment": comment,
        "reaction": reaction,
    }


@pytest_asyncio.fixture
async def empty_client(session_factory, app_under_test: FastAPI):
    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app_under_test.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app_under_test)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app_under_test.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_claim_flow_claims_site_and_locks_claim_page(
    empty_client: AsyncClient,
    db: AsyncSession,
):
    resp = await empty_client.get("/claim")
    assert resp.status_code == 200
    assert "Claim this Family Book" in resp.text

    claim_resp = await empty_client.post(
        "/claim",
        data={
            "first_name": "Taylor",
            "last_name": "Martin",
            "email": "taylor@example.com",
            "family_name": "Martin Family Book",
        },
        follow_redirects=False,
    )

    assert claim_resp.status_code == 303
    assert claim_resp.headers["location"] == "/setup"
    assert empty_client.cookies.get("session")

    claimed = get_site_settings(force_reload=True)
    assert claimed.state == "claimed"
    assert claimed.title == "Martin Family Book"

    result = await db.execute(select(Person))
    people = result.scalars().all()
    assert len(people) == 1
    assert people[0].is_admin is True
    assert people[0].contact_email == "taylor@example.com"

    locked_resp = await empty_client.get("/claim")
    assert locked_resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_demo_cleanup_removes_seed_records_and_media_files(
    admin_client: AsyncClient,
    seeded_db: AsyncSession,
):
    claim_site(title="Rivera Family Book", claimed_by="alex-000-0000-0000-000000000002")
    records = _seed_records()
    primary_person_id = records["persons"][0]["id"]
    secondary_person_id = records["persons"][1]["id"]

    for payload in records["persons"]:
        person = Person(
            id=payload["id"],
            first_name=payload["first_name"],
            last_name=payload["last_name"],
            is_admin=payload.get("is_admin", False),
            is_root=payload.get("is_root", False),
            contact_email=payload.get("contact_email"),
            source=payload.get("source", "manual"),
        )
        seeded_db.add(person)
    await seeded_db.flush()

    parent_child = ParentChild(
        id=records["parent_child"]["id"],
        parent_id=records["parent_child"]["parent_id"],
        child_id=records["parent_child"]["child_id"],
        source=records["parent_child"].get("source", "manual"),
    )
    partnership = Partnership(
        id=records["partnership"]["id"],
        person_a_id=min(records["partnership"]["person_a_id"], records["partnership"]["person_b_id"]),
        person_b_id=max(records["partnership"]["person_a_id"], records["partnership"]["person_b_id"]),
        source=records["partnership"].get("source", "manual"),
    )

    media_dir = Path(get_settings().DATA_DIR) / "media"
    (media_dir / "resized").mkdir(parents=True, exist_ok=True)
    (media_dir / "thumbnails").mkdir(parents=True, exist_ok=True)
    original = media_dir / "demo-seed.jpg"
    resized = media_dir / "resized" / "demo-seed.jpg"
    thumb = media_dir / "thumbnails" / "demo-seed.jpg"
    for file_path in (original, resized, thumb):
        file_path.write_bytes(b"demo")

    media = Media(
        id="demo-media-1",
        person_id=primary_person_id,
        file_path="demo-seed.jpg",
        resized_path="resized/demo-seed.jpg",
        video_thumbnail_path="thumbnails/demo-seed.jpg",
        media_type="image",
        source="manual",
    )
    moment = Moment(
        id=records["moment"]["id"],
        person_id=primary_person_id,
        kind=records["moment"]["kind"],
        title=records["moment"].get("title"),
        body=records["moment"].get("body"),
        source=records["moment"].get("source", "manual"),
    )
    moment.media_ids = ["demo-media-1"]
    comment = MomentComment(
        id=records["comment"]["id"],
        moment_id=records["moment"]["id"],
        person_id=secondary_person_id,
        body=records["comment"]["body"],
    )
    reaction = MomentReaction(
        id=records["reaction"]["id"],
        moment_id=records["moment"]["id"],
        person_id=secondary_person_id,
        emoji=records["reaction"]["emoji"],
    )

    seeded_db.add_all([parent_child, partnership, media, moment, comment, reaction])
    await seeded_db.commit()

    resp = await admin_client.post("/admin/demo-cleanup")
    assert resp.status_code == 200
    assert 'id="admin-demo-data"></div>' in resp.text

    for model, record_id in (
        (MomentComment, comment.id),
        (MomentReaction, reaction.id),
        (Moment, moment.id),
        (ParentChild, parent_child.id),
        (Partnership, partnership.id),
        (Media, media.id),
    ):
        result = await seeded_db.execute(select(model).where(model.id == record_id))
        assert result.scalar_one_or_none() is None

    for person in records["persons"]:
        result = await seeded_db.execute(select(Person).where(Person.id == person["id"]))
        assert result.scalar_one_or_none() is None

    assert not original.exists()
    assert not resized.exists()
    assert not thumb.exists()


@pytest.mark.asyncio
async def test_setup_wizard_steps_add_members_and_generate_invites(
    admin_client: AsyncClient,
    seeded_db: AsyncSession,
):
    claim_site(title="Rivera Family Book", claimed_by="alex-000-0000-0000-000000000002")

    page = await admin_client.get("/setup")
    assert page.status_code == 200
    assert "Setup wizard" in page.text

    step1 = await admin_client.get("/setup/step/1")
    assert step1.status_code == 200
    assert "Remove demo data?" in step1.text

    step2 = await admin_client.post("/setup/clean", data={"action": "keep"})
    assert step2.status_code == 200
    assert "Add family members" in step2.text

    add_resp = await admin_client.post(
        "/setup/add-member",
        data={
            "first_name": "Nina",
            "last_name": "Rivera",
            "relationship": "child",
            "email": "nina@example.com",
            "branch": "rivera",
        },
    )
    assert add_resp.status_code == 200
    assert "Nina Rivera" in add_resp.text

    person_result = await seeded_db.execute(select(Person).where(Person.contact_email == "nina@example.com"))
    nina = person_result.scalar_one()
    assert nina.created_by == "alex-000-0000-0000-000000000002"

    edge_result = await seeded_db.execute(
        select(ParentChild).where(
            ParentChild.parent_id == "alex-000-0000-0000-000000000002",
            ParentChild.child_id == nina.id,
        )
    )
    assert edge_result.scalar_one_or_none() is not None

    step3 = await admin_client.get("/setup/invite-step")
    assert step3.status_code == 200
    assert "Invite your family" in step3.text

    invite_resp = await admin_client.post(f"/setup/invite/{nina.id}")
    assert invite_resp.status_code == 200
    assert "/invite/" in invite_resp.text

    invite_result = await seeded_db.execute(select(Invite).where(Invite.person_id == nina.id))
    assert invite_result.scalar_one_or_none() is not None
