"""
Idempotent seed loader. Reads data/family_tree.json and upserts all rows.
Run: uv run python -m app.seed
"""
import asyncio
import json
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, engine
from app.models.base import Base
from app.models.person import Person
from app.models.relationships import ParentChild, Partnership


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
        else:
            person = Person(**{k: v for k, v in p.items() if k != "languages"})
            if "languages" in p:
                person.languages = p["languages"]
            session.add(person)
            person_count += 1

    rel_count = 0
    for r in data.get("parent_child", []):
        result = await session.execute(select(ParentChild).where(ParentChild.id == r["id"]))
        if not result.scalar_one_or_none():
            session.add(ParentChild(**r))
            rel_count += 1

    partnership_count = 0
    for p in data.get("partnerships", []):
        result = await session.execute(select(Partnership).where(Partnership.id == p["id"]))
        if not result.scalar_one_or_none():
            session.add(Partnership(**p))
            partnership_count += 1

    await session.commit()
    total_rels = rel_count + partnership_count
    print(f"Seeded {person_count} new persons, {total_rels} new relationships")


async def main():
    async with async_session_factory() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
