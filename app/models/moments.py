import enum
import json

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_uuid, utcnow
from datetime import datetime


class MomentKind(str, enum.Enum):
    photo = "photo"
    video = "video"
    text = "text"
    milestone = "milestone"
    memorial = "memorial"


class MilestoneType(str, enum.Enum):
    birth = "birth"
    first_steps = "first_steps"
    first_words = "first_words"
    first_day_school = "first_day_school"
    graduation = "graduation"
    engagement = "engagement"
    marriage = "marriage"
    divorce = "divorce"
    new_home = "new_home"
    travel = "travel"
    death = "death"
    birthday = "birthday"
    anniversary = "anniversary"
    custom = "custom"


class MomentSource(str, enum.Enum):
    manual = "manual"
    whatsapp_import = "whatsapp_import"
    facebook_import = "facebook_import"
    instagram_import = "instagram_import"
    auto_generated = "auto_generated"


class MomentVisibility(str, enum.Enum):
    members = "members"
    admins = "admins"
    hidden = "hidden"


class OccurredPrecision(str, enum.Enum):
    exact = "exact"
    day = "day"
    month = "month"
    year = "year"


class Moment(Base):
    __tablename__ = "moments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(300), default=None)
    body: Mapped[str | None] = mapped_column(Text, default=None)
    _media_ids: Mapped[str | None] = mapped_column("media_ids", Text, default="[]")
    milestone_type: Mapped[str | None] = mapped_column(String(30), default=None)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow)
    occurred_precision: Mapped[str] = mapped_column(
        String(10), default=OccurredPrecision.exact.value
    )
    source: Mapped[str] = mapped_column(String(30), default=MomentSource.manual.value)
    visibility: Mapped[str] = mapped_column(String(20), default=MomentVisibility.members.value)
    posted_by: Mapped[str | None] = mapped_column(String(36), default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    @property
    def media_ids(self) -> list[str]:
        if self._media_ids:
            return json.loads(self._media_ids)
        return []

    @media_ids.setter
    def media_ids(self, value: list[str]) -> None:
        self._media_ids = json.dumps(value)

    def __repr__(self) -> str:
        return f"<Moment id={self.id[:8]} kind={self.kind}>"


class MomentReaction(Base):
    __tablename__ = "moment_reactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    moment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("moments.id", ondelete="CASCADE")
    )
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    emoji: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        __import__("sqlalchemy").UniqueConstraint(
            "moment_id", "person_id", name="uq_reaction_per_person"
        ),
    )


class MomentComment(Base):
    __tablename__ = "moment_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    moment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("moments.id", ondelete="CASCADE")
    )
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    body: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
