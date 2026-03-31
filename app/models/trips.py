"""Trip Albums — shared group photo collections for family vacations."""

import enum
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid, utcnow


class TripVisibility(str, enum.Enum):
    members = "members"
    admins = "admins"
    hidden = "hidden"


class TripParticipantRole(str, enum.Enum):
    organizer = "organizer"
    contributor = "contributor"
    viewer = "viewer"


class Trip(Base, TimestampMixin):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    start_date: Mapped[str | None] = mapped_column(String(10), default=None)  # ISO 8601 date
    end_date: Mapped[str | None] = mapped_column(String(10), default=None)
    cover_media_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("media.id", ondelete="SET NULL"), default=None
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    visibility: Mapped[str] = mapped_column(
        String(20), default=TripVisibility.members.value
    )
    invite_token: Mapped[str | None] = mapped_column(
        String(64), unique=True, default=None
    )

    def __repr__(self) -> str:
        return f"<Trip id={self.id[:8]} name={self.name!r}>"


class TripParticipant(Base):
    __tablename__ = "trip_participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    trip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trips.id", ondelete="CASCADE")
    )
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(
        String(20), default=TripParticipantRole.contributor.value
    )
    joined_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        UniqueConstraint("trip_id", "person_id", name="uq_trip_participant"),
    )

    def __repr__(self) -> str:
        return f"<TripParticipant trip={self.trip_id[:8]} person={self.person_id[:8]}>"


class TripMoment(Base):
    __tablename__ = "trip_moments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    trip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trips.id", ondelete="CASCADE")
    )
    moment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("moments.id", ondelete="CASCADE")
    )
    added_at: Mapped[datetime] = mapped_column(default=utcnow)
    added_by: Mapped[str | None] = mapped_column(String(36), default=None)

    __table_args__ = (
        UniqueConstraint("trip_id", "moment_id", name="uq_trip_moment"),
    )

    def __repr__(self) -> str:
        return f"<TripMoment trip={self.trip_id[:8]} moment={self.moment_id[:8]}>"
