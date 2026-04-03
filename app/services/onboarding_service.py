import json
import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.media import Media
from app.models.moments import Moment, MomentComment, MomentReaction
from app.models.person import Person
from app.models.relationships import ParentChild, Partnership
from app.models.trips import Trip, TripMoment
from app.services.audit_service import log_audit


SEED_SOURCE = "seed"
_SEED_FILE = Path(__file__).resolve().parents[2] / "data" / "family_tree.json"


@dataclass
class SeedCatalog:
    person_ids: set[str]
    moment_ids: set[str]
    comment_ids: set[str]
    reaction_ids: set[str]
    parent_child_ids: set[str]
    partnership_ids: set[str]
    trip_ids: set[str]
    trip_moment_ids: set[str]


def load_seed_catalog() -> SeedCatalog:
    data = json.loads(_SEED_FILE.read_text(encoding="utf-8"))
    return SeedCatalog(
        person_ids={item["id"] for item in data.get("persons", [])},
        moment_ids={item["id"] for item in data.get("moments", [])},
        comment_ids={item["id"] for item in data.get("moment_comments", [])},
        reaction_ids={item["id"] for item in data.get("moment_reactions", [])},
        parent_child_ids={item["id"] for item in data.get("parent_child", [])},
        partnership_ids={item["id"] for item in data.get("partnerships", [])},
        trip_ids={item["id"] for item in data.get("trips", [])},
        trip_moment_ids={item["id"] for item in data.get("trip_moments", [])},
    )


def _seed_match(model, id_field: str, ids: set[str], source_field: str | None = "source"):
    conditions = []
    if ids:
        conditions.append(getattr(model, id_field).in_(ids))
    if source_field and hasattr(model, source_field):
        conditions.append(getattr(model, source_field) == SEED_SOURCE)
    if not conditions:
        return None
    return or_(*conditions)


async def get_seed_data_counts(db: AsyncSession) -> dict[str, int]:
    catalog = load_seed_catalog()
    counts: dict[str, int] = {}
    specs = [
        ("persons", Person, "id", catalog.person_ids),
        ("moments", Moment, "id", catalog.moment_ids),
        ("relationships", ParentChild, "id", catalog.parent_child_ids),
        ("partnerships", Partnership, "id", catalog.partnership_ids),
    ]
    for key, model, id_field, ids in specs:
        match = _seed_match(model, id_field, ids)
        if match is None:
            counts[key] = 0
            continue
        counts[key] = (await db.execute(select(func.count()).select_from(model).where(match))).scalar() or 0
    counts["total"] = sum(counts.values())
    return counts


async def _delete_media_files(media: Media) -> None:
    data_dir = Path(get_settings().DATA_DIR)
    relative_paths = [media.file_path, media.video_thumbnail_path, media.resized_path]
    for relative_path in relative_paths:
        if not relative_path:
            continue
        path = data_dir / "media" / relative_path
        if path.exists():
            path.unlink()


async def remove_demo_data(db: AsyncSession) -> dict[str, int]:
    catalog = load_seed_catalog()

    demo_moment_match = _seed_match(Moment, "id", catalog.moment_ids)
    if demo_moment_match is None:
        return {
            "comments": 0,
            "reactions": 0,
            "trip_moments": 0,
            "trips": 0,
            "moments": 0,
            "partnerships": 0,
            "parent_child": 0,
            "persons": 0,
            "media": 0,
        }

    demo_moments = (await db.execute(select(Moment).where(demo_moment_match))).scalars().all()
    demo_moment_ids = {moment.id for moment in demo_moments}
    demo_media_ids = {
        media_id
        for moment in demo_moments
        for media_id in moment.media_ids
        if media_id and not media_id.startswith("/static/")
    }
    demo_media: dict[str, Media] = {}
    if demo_media_ids:
        result = await db.execute(select(Media).where(Media.id.in_(demo_media_ids)))
        demo_media = {media.id: media for media in result.scalars().all()}

    counts: dict[str, int] = {}

    comment_match = _seed_match(MomentComment, "id", catalog.comment_ids, source_field=None)
    counts["comments"] = 0
    if comment_match is not None:
        counts["comments"] = (await db.execute(delete(MomentComment).where(comment_match))).rowcount or 0

    reaction_match = _seed_match(MomentReaction, "id", catalog.reaction_ids, source_field=None)
    counts["reactions"] = 0
    if reaction_match is not None:
        counts["reactions"] = (await db.execute(delete(MomentReaction).where(reaction_match))).rowcount or 0

    trip_moment_conditions = []
    if catalog.trip_moment_ids:
        trip_moment_conditions.append(TripMoment.id.in_(catalog.trip_moment_ids))
    if demo_moment_ids:
        trip_moment_conditions.append(TripMoment.moment_id.in_(demo_moment_ids))
    counts["trip_moments"] = 0
    if trip_moment_conditions:
        counts["trip_moments"] = (
            await db.execute(delete(TripMoment).where(or_(*trip_moment_conditions)))
        ).rowcount or 0

    trip_match = _seed_match(Trip, "id", catalog.trip_ids, source_field=None)
    counts["trips"] = 0
    if trip_match is not None:
        counts["trips"] = (await db.execute(delete(Trip).where(trip_match))).rowcount or 0

    counts["moments"] = (await db.execute(delete(Moment).where(demo_moment_match))).rowcount or 0

    partnership_match = _seed_match(Partnership, "id", catalog.partnership_ids)
    counts["partnerships"] = 0
    if partnership_match is not None:
        counts["partnerships"] = (await db.execute(delete(Partnership).where(partnership_match))).rowcount or 0

    parent_child_match = _seed_match(ParentChild, "id", catalog.parent_child_ids)
    counts["parent_child"] = 0
    if parent_child_match is not None:
        counts["parent_child"] = (await db.execute(delete(ParentChild).where(parent_child_match))).rowcount or 0

    person_match = _seed_match(Person, "id", catalog.person_ids)
    counts["persons"] = 0
    if person_match is not None:
        counts["persons"] = (await db.execute(delete(Person).where(person_match))).rowcount or 0

    counts["media"] = 0
    if demo_media_ids:
        other_moments = (
            await db.execute(select(Moment._media_ids).where(Moment.id.notin_(demo_moment_ids)))
        ).scalars().all()
        for media_id in demo_media_ids:
            still_used = any(media_id in (json.loads(value) if value else []) for value in other_moments)
            if still_used:
                continue
            media = demo_media.get(media_id)
            if not media:
                continue
            await _delete_media_files(media)
            existing_media = (await db.execute(select(Media).where(Media.id == media_id))).scalar_one_or_none()
            if existing_media:
                await db.delete(existing_media)
            counts["media"] += 1

    await db.flush()
    return counts


async def add_setup_member(
    db: AsyncSession,
    *,
    admin: Person,
    first_name: str,
    last_name: str,
    relationship: str,
    email: str | None,
    branch: str | None,
) -> tuple[Person, str | None]:
    person = Person(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        contact_email=(email or "").strip().lower() or None,
        branch=(branch or "").strip() or None,
        created_by=admin.id,
    )
    db.add(person)
    await db.flush()

    await log_audit(
        db,
        admin.id,
        "create",
        "person",
        person.id,
        new_value={"first_name": person.first_name, "last_name": person.last_name},
    )

    note: str | None = None
    if relationship == "partner":
        person_a_id, person_b_id = sorted([admin.id, person.id])
        partnership = Partnership(
            person_a_id=person_a_id,
            person_b_id=person_b_id,
            source="manual",
            created_by=admin.id,
        )
        db.add(partnership)
        await db.flush()
        await log_audit(
            db,
            admin.id,
            "create",
            "partnership",
            partnership.id,
            new_value={"person_a_id": person_a_id, "person_b_id": person_b_id},
        )
    elif relationship == "parent":
        rel = ParentChild(parent_id=person.id, child_id=admin.id, source="manual", created_by=admin.id)
        db.add(rel)
        await db.flush()
        await log_audit(
            db,
            admin.id,
            "create",
            "parent_child",
            rel.id,
            new_value={"parent_id": person.id, "child_id": admin.id, "kind": rel.kind},
        )
    elif relationship == "child":
        rel = ParentChild(parent_id=admin.id, child_id=person.id, source="manual", created_by=admin.id)
        db.add(rel)
        await db.flush()
        await log_audit(
            db,
            admin.id,
            "create",
            "parent_child",
            rel.id,
            new_value={"parent_id": admin.id, "child_id": person.id, "kind": rel.kind},
        )
    elif relationship == "sibling":
        parent_ids = (
            await db.execute(select(ParentChild.parent_id).where(ParentChild.child_id == admin.id))
        ).scalars().all()
        if parent_ids:
            for parent_id in parent_ids:
                rel = ParentChild(parent_id=parent_id, child_id=person.id, source="manual", created_by=admin.id)
                db.add(rel)
                await db.flush()
                await log_audit(
                    db,
                    admin.id,
                    "create",
                    "parent_child",
                    rel.id,
                    new_value={"parent_id": parent_id, "child_id": person.id, "kind": rel.kind},
                )
        else:
            note = "Added without a relationship edge because your profile has no parents yet."

    return person, note
