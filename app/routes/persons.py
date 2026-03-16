from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin, require_auth
from app.database import get_db
from app.models.person import Person, Visibility
from app.schemas import (
    PersonCreate,
    PersonDetail,
    PersonSummary,
    PersonUpdate,
    person_to_detail,
    person_to_summary,
)
from app.services.audit_service import log_audit

router = APIRouter(prefix="/api/persons", tags=["persons"])


@router.get("", response_model=list[PersonSummary])
async def list_persons(
    search: str | None = Query(None),
    branch: str | None = Query(None),
    country: str | None = Query(None),
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    query = select(Person).where(Person.visibility != Visibility.hidden.value)

    if search:
        like = f"%{search}%"
        query = query.where(
            (Person.first_name.ilike(like))
            | (Person.last_name.ilike(like))
            | (Person.nickname.ilike(like))
        )
    if branch:
        query = query.where(Person.branch == branch)
    if country:
        query = query.where(Person.residence_country_code == country)

    query = query.order_by(Person.last_name, Person.first_name)
    result = await db.execute(query)
    persons = result.scalars().all()
    return [person_to_summary(p) for p in persons]


@router.get("/{person_id}", response_model=PersonDetail)
async def get_person(
    person_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    if person.visibility == Visibility.hidden.value and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not visible")
    return person_to_detail(person)


@router.post("", response_model=PersonDetail, status_code=status.HTTP_201_CREATED)
async def create_person(
    body: PersonCreate,
    current_user: Person = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    person = Person(
        first_name=body.first_name,
        last_name=body.last_name,
        patronymic=body.patronymic,
        birth_last_name=body.birth_last_name,
        nickname=body.nickname,
        name_display_order=body.name_display_order,
        gender=body.gender,
        birth_date_raw=body.birth_date_raw,
        birth_date=body.birth_date,
        birth_date_precision=body.birth_date_precision,
        death_date_raw=body.death_date_raw,
        death_date=body.death_date,
        death_date_precision=body.death_date_precision,
        is_living=body.is_living,
        birth_place=body.birth_place,
        birth_country_code=body.birth_country_code,
        residence_place=body.residence_place,
        residence_country_code=body.residence_country_code,
        burial_place=body.burial_place,
        bio=body.bio,
        contact_whatsapp=body.contact_whatsapp,
        contact_telegram=body.contact_telegram,
        contact_signal=body.contact_signal,
        contact_email=body.contact_email,
        branch=body.branch,
        source=body.source,
        created_by=current_user.id,
    )
    person.languages = body.languages
    db.add(person)
    await db.flush()

    await log_audit(db, current_user.id, "create", "person", person.id, new_value={
        "first_name": person.first_name,
        "last_name": person.last_name,
    })

    return person_to_detail(person)


@router.put("/{person_id}", response_model=PersonDetail)
async def update_person(
    person_id: str,
    body: PersonUpdate,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    # Allow self-edit or admin
    if person_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    old_data = {"first_name": person.first_name, "last_name": person.last_name}
    update_data = body.model_dump(exclude_unset=True)

    # Handle languages separately
    if "languages" in update_data:
        person.languages = update_data.pop("languages")

    for field, value in update_data.items():
        setattr(person, field, value)

    await db.flush()
    await log_audit(db, current_user.id, "update", "person", person.id,
                    old_value=old_data,
                    new_value={"fields_changed": list(body.model_dump(exclude_unset=True).keys())})

    return person_to_detail(person)


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(
    person_id: str,
    current_user: Person = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    await log_audit(db, current_user.id, "delete", "person", person.id,
                    old_value={"first_name": person.first_name, "last_name": person.last_name})

    await db.delete(person)
    await db.flush()
