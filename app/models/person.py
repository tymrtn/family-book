import enum
import json

from sqlalchemy import Boolean, Index, LargeBinary, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid, utcnow


class NameDisplayOrder(str, enum.Enum):
    western = "western"
    eastern = "eastern"
    patronymic = "patronymic"


class Gender(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"


class DatePrecision(str, enum.Enum):
    exact = "exact"
    month = "month"
    year = "year"
    decade = "decade"
    approximate = "approximate"


class Visibility(str, enum.Enum):
    visible = "visible"
    hidden = "hidden"
    memorial = "memorial"


class AccountState(str, enum.Enum):
    active = "active"
    pending = "pending"
    suspended = "suspended"


class PersonSource(str, enum.Enum):
    manual = "manual"
    facebook_oauth = "facebook_oauth"
    gedcom_import = "gedcom_import"
    whatsapp_import = "whatsapp_import"
    messenger_import = "messenger_import"
    federation = "federation"
    matrix = "matrix"


class Person(Base, TimestampMixin):
    __tablename__ = "persons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    first_name: Mapped[str] = mapped_column(String(200))
    last_name: Mapped[str] = mapped_column(String(200))
    patronymic: Mapped[str | None] = mapped_column(String(200), default=None)
    birth_last_name: Mapped[str | None] = mapped_column(String(200), default=None)
    nickname: Mapped[str | None] = mapped_column(String(100), default=None)
    name_display_order: Mapped[str] = mapped_column(
        String(20), default=NameDisplayOrder.western.value
    )
    gender: Mapped[str | None] = mapped_column(String(10), default=None)

    birth_date_raw: Mapped[str | None] = mapped_column(String(50), default=None)
    birth_date: Mapped[str | None] = mapped_column(String(10), default=None)  # ISO 8601
    birth_date_precision: Mapped[str | None] = mapped_column(String(20), default=None)
    death_date_raw: Mapped[str | None] = mapped_column(String(50), default=None)
    death_date: Mapped[str | None] = mapped_column(String(10), default=None)
    death_date_precision: Mapped[str | None] = mapped_column(String(20), default=None)
    is_living: Mapped[bool] = mapped_column(Boolean, default=True)

    birth_place: Mapped[str | None] = mapped_column(String(300), default=None)
    birth_country_code: Mapped[str | None] = mapped_column(String(2), default=None)
    residence_place: Mapped[str | None] = mapped_column(String(300), default=None)
    residence_country_code: Mapped[str | None] = mapped_column(String(2), default=None)
    burial_place: Mapped[str | None] = mapped_column(String(300), default=None)

    _languages: Mapped[str | None] = mapped_column("languages", Text, default="[]")
    bio: Mapped[str | None] = mapped_column(String(2000), default=None)

    contact_whatsapp: Mapped[str | None] = mapped_column(String(20), default=None)
    contact_telegram: Mapped[str | None] = mapped_column(String(100), default=None)
    contact_signal: Mapped[str | None] = mapped_column(String(20), default=None)
    contact_email: Mapped[str | None] = mapped_column(String(320), default=None)

    photo_url: Mapped[str | None] = mapped_column(String(2000), default=None)
    branch: Mapped[str | None] = mapped_column(String(100), default=None)

    is_root: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility: Mapped[str] = mapped_column(String(20), default=Visibility.visible.value)
    account_state: Mapped[str] = mapped_column(String(20), default=AccountState.active.value)

    facebook_id: Mapped[str | None] = mapped_column(String(100), unique=True, default=None)
    facebook_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)
    facebook_token_expires: Mapped[str | None] = mapped_column(String(30), default=None)

    source: Mapped[str] = mapped_column(String(30), default=PersonSource.manual.value)
    created_by: Mapped[str | None] = mapped_column(String(36), default=None)

    __table_args__ = (
        Index("idx_persons_facebook_id", "facebook_id", unique=True, sqlite_where=text("facebook_id IS NOT NULL")),
        Index("idx_persons_country_code", "residence_country_code"),
        Index("idx_persons_is_root", "is_root", sqlite_where=text("is_root = 1")),
    )

    @property
    def languages(self) -> list[str]:
        if self._languages:
            return json.loads(self._languages)
        return []

    @languages.setter
    def languages(self, value: list[str]) -> None:
        self._languages = json.dumps(value)

    @property
    def display_name(self) -> str:
        if self.is_root:
            return "Семья Володиных"
        if self.name_display_order == NameDisplayOrder.eastern.value:
            return f"{self.last_name} {self.first_name}"
        if self.name_display_order == NameDisplayOrder.patronymic.value and self.patronymic:
            return f"{self.last_name} {self.first_name} {self.patronymic}"
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Person id={self.id[:8]} name={self.display_name!r}>"
