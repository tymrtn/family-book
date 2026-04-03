"""
Idempotent seed loader. Reads data/family_tree.json and upserts all rows.
Run: uv run python -m app.seed
"""
import asyncio
import json
import os
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, engine
from app.models.base import Base
from app.models.moments import Moment, MomentComment, MomentReaction
from app.models.person import Person
from app.models.relationships import ParentChild, Partnership
from app.services.onboarding_service import SEED_SOURCE


SEED_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "family_tree.json")


async def seed(session: AsyncSession) -> None:
    with open(SEED_FILE) as f:
        data = json.load(f)

    person_count = 0
    for p in data.get("persons", []):
        result = await session.execute(select(Person).where(Person.id == p["id"]))
        existing = result.scalar_one_or_none()
        if existing:
            # Update fields
            for k, v in p.items():
                if k == "languages":
                    existing.languages = v
                elif k != "id":
                    setattr(existing, k, v)
            existing.source = SEED_SOURCE
        else:
            person_data = {k: v for k, v in p.items() if k != "languages"}
            person_data["source"] = SEED_SOURCE
            person = Person(**person_data)
            if "languages" in p:
                person.languages = p["languages"]
            session.add(person)
            person_count += 1

    rel_count = 0
    for r in data.get("parent_child", []):
        result = await session.execute(select(ParentChild).where(ParentChild.id == r["id"]))
        existing = result.scalar_one_or_none()
        if existing:
            existing.source = SEED_SOURCE
        else:
            rel_data = dict(r)
            rel_data["source"] = SEED_SOURCE
            session.add(ParentChild(**rel_data))
            rel_count += 1

    partnership_count = 0
    for p in data.get("partnerships", []):
        result = await session.execute(select(Partnership).where(Partnership.id == p["id"]))
        existing = result.scalar_one_or_none()
        if existing:
            existing.source = SEED_SOURCE
        else:
            partnership_data = dict(p)
            partnership_data["source"] = SEED_SOURCE
            session.add(Partnership(**partnership_data))
            partnership_count += 1

    moment_count = 0
    for m in data.get("moments", []):
        moment_data = {k: v for k, v in m.items()}
        # Parse occurred_at from string to datetime
        if "occurred_at" in moment_data and isinstance(moment_data["occurred_at"], str):
            moment_data["occurred_at"] = datetime.fromisoformat(moment_data["occurred_at"])
        # Handle media_ids list → JSON column
        media_ids_list = moment_data.pop("media_ids", None)

        result = await session.execute(select(Moment).where(Moment.id == m["id"]))
        existing = result.scalar_one_or_none()
        if existing:
            # Update fields on existing moments
            for k, v in moment_data.items():
                if k != "id":
                    setattr(existing, k, v)
            existing.source = SEED_SOURCE
            if media_ids_list is not None:
                existing.media_ids = media_ids_list
        else:
            moment_data["source"] = SEED_SOURCE
            moment_obj = Moment(**moment_data)
            if media_ids_list:
                moment_obj.media_ids = media_ids_list
            session.add(moment_obj)
            moment_count += 1

    reaction_count = 0
    for r in data.get("moment_reactions", []):
        result = await session.execute(select(MomentReaction).where(MomentReaction.id == r["id"]))
        if not result.scalar_one_or_none():
            session.add(MomentReaction(**r))
            reaction_count += 1

    comment_count = 0
    for c in data.get("moment_comments", []):
        result = await session.execute(select(MomentComment).where(MomentComment.id == c["id"]))
        if not result.scalar_one_or_none():
            session.add(MomentComment(**c))
            comment_count += 1

    await session.commit()
    total_rels = rel_count + partnership_count
    print(f"Seeded {person_count} new persons, {total_rels} new relationships, "
          f"{moment_count} moments, {reaction_count} reactions, {comment_count} comments")


async def main():
    async with async_session_factory() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
