from datetime import datetime
from pydantic import BaseModel, Field


# --- Person ---

class PersonCreate(BaseModel):
    first_name: str = Field(max_length=200)
    last_name: str = Field(max_length=200)
    patronymic: str | None = Field(None, max_length=200)
    birth_last_name: str | None = Field(None, max_length=200)
    nickname: str | None = Field(None, max_length=100)
    name_display_order: str = "western"
    gender: str | None = None
    birth_date_raw: str | None = Field(None, max_length=50)
    birth_date: str | None = Field(None, max_length=10)
    birth_date_precision: str | None = None
    death_date_raw: str | None = Field(None, max_length=50)
    death_date: str | None = Field(None, max_length=10)
    death_date_precision: str | None = None
    is_living: bool = True
    birth_place: str | None = Field(None, max_length=300)
    birth_country_code: str | None = Field(None, max_length=2)
    residence_place: str | None = Field(None, max_length=300)
    residence_country_code: str | None = Field(None, max_length=2)
    burial_place: str | None = Field(None, max_length=300)
    languages: list[str] = []
    bio: str | None = Field(None, max_length=2000)
    contact_whatsapp: str | None = None
    contact_telegram: str | None = None
    contact_signal: str | None = None
    contact_email: str | None = None
    branch: str | None = Field(None, max_length=100)
    source: str = "manual"


class PersonUpdate(BaseModel):
    first_name: str | None = Field(None, max_length=200)
    last_name: str | None = Field(None, max_length=200)
    patronymic: str | None = Field(None, max_length=200)
    birth_last_name: str | None = Field(None, max_length=200)
    nickname: str | None = Field(None, max_length=100)
    name_display_order: str | None = None
    gender: str | None = None
    birth_date_raw: str | None = Field(None, max_length=50)
    birth_date: str | None = Field(None, max_length=10)
    birth_date_precision: str | None = None
    death_date_raw: str | None = Field(None, max_length=50)
    death_date: str | None = Field(None, max_length=10)
    death_date_precision: str | None = None
    is_living: bool | None = None
    birth_place: str | None = Field(None, max_length=300)
    birth_country_code: str | None = Field(None, max_length=2)
    residence_place: str | None = Field(None, max_length=300)
    residence_country_code: str | None = Field(None, max_length=2)
    burial_place: str | None = Field(None, max_length=300)
    languages: list[str] | None = None
    bio: str | None = Field(None, max_length=2000)
    contact_whatsapp: str | None = None
    contact_telegram: str | None = None
    contact_signal: str | None = None
    contact_email: str | None = None
    branch: str | None = Field(None, max_length=100)
    visibility: str | None = None


class PersonSummary(BaseModel):
    id: str
    display_name: str
    nickname: str | None
    photo_url: str | None
    residence_country_code: str | None
    branch: str | None
    is_living: bool
    visibility: str

    model_config = {"from_attributes": True}


class PersonDetail(PersonSummary):
    first_name: str | None = None  # None for root person
    last_name: str | None = None   # None for root person
    patronymic: str | None = None
    birth_last_name: str | None = None
    gender: str | None = None
    birth_date_raw: str | None = None
    birth_date: str | None = None
    birth_date_precision: str | None = None
    death_date_raw: str | None = None
    death_date: str | None = None
    death_date_precision: str | None = None
    birth_place: str | None = None
    birth_country_code: str | None = None
    residence_place: str | None = None
    burial_place: str | None = None
    languages: list[str] = []
    bio: str | None = None
    contact_whatsapp: str | None = None
    contact_telegram: str | None = None
    contact_signal: str | None = None
    contact_email: str | None = None
    is_admin: bool = False
    is_root: bool = False
    source: str = "manual"
    created_at: datetime | None = None


def person_to_summary(person) -> PersonSummary:
    """Convert a Person ORM object to PersonSummary, respecting root redaction."""
    return PersonSummary(
        id=person.id,
        display_name=person.display_name,
        nickname=person.nickname if not person.is_root else None,
        photo_url=person.photo_url,
        residence_country_code=person.residence_country_code,
        branch=person.branch,
        is_living=person.is_living,
        visibility=person.visibility,
    )


def person_to_detail(person) -> PersonDetail:
    """Convert a Person ORM object to PersonDetail, respecting root redaction."""
    if person.is_root:
        return PersonDetail(
            id=person.id,
            display_name=person.display_name,
            nickname=None,
            photo_url=person.photo_url,
            residence_country_code=person.residence_country_code,
            branch=person.branch,
            is_living=person.is_living,
            visibility=person.visibility,
            first_name=None,
            last_name=None,
            is_root=True,
            source=person.source,
            created_at=person.created_at,
        )
    return PersonDetail(
        id=person.id,
        display_name=person.display_name,
        nickname=person.nickname,
        photo_url=person.photo_url,
        residence_country_code=person.residence_country_code,
        branch=person.branch,
        is_living=person.is_living,
        visibility=person.visibility,
        first_name=person.first_name,
        last_name=person.last_name,
        patronymic=person.patronymic,
        birth_last_name=person.birth_last_name,
        gender=person.gender,
        birth_date_raw=person.birth_date_raw,
        birth_date=person.birth_date,
        birth_date_precision=person.birth_date_precision,
        death_date_raw=person.death_date_raw,
        death_date=person.death_date,
        death_date_precision=person.death_date_precision,
        birth_place=person.birth_place,
        birth_country_code=person.birth_country_code,
        residence_place=person.residence_place,
        burial_place=person.burial_place,
        languages=person.languages,
        bio=person.bio,
        contact_whatsapp=person.contact_whatsapp,
        contact_telegram=person.contact_telegram,
        contact_signal=person.contact_signal,
        contact_email=person.contact_email,
        is_admin=person.is_admin,
        is_root=person.is_root,
        source=person.source,
        created_at=person.created_at,
    )


# --- ParentChild ---

class ParentChildCreate(BaseModel):
    parent_id: str
    child_id: str
    kind: str = "biological"
    confidence: str | None = "confirmed"
    source: str = "manual"
    source_detail: str | None = None
    notes: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ParentChildResponse(BaseModel):
    id: str
    parent_id: str
    child_id: str
    kind: str
    confidence: str | None
    source: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Partnership ---

class PartnershipCreate(BaseModel):
    person_a_id: str
    person_b_id: str
    kind: str = "married"
    status: str = "active"
    start_date: str | None = None
    start_date_precision: str | None = None
    end_date: str | None = None
    end_date_precision: str | None = None
    source: str = "manual"
    notes: str | None = None


class PartnershipUpdate(BaseModel):
    status: str | None = None
    end_date: str | None = None
    end_date_precision: str | None = None
    notes: str | None = None


class PartnershipResponse(BaseModel):
    id: str
    person_a_id: str
    person_b_id: str
    kind: str
    status: str
    start_date: str | None = None
    end_date: str | None = None
    source: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Tree ---

class TreeResponse(BaseModel):
    root_id: str
    persons: list[PersonSummary]
    parent_child: list[ParentChildResponse]
    partnerships: list[PartnershipResponse]
