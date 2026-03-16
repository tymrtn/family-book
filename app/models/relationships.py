import enum

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_uuid, utcnow
from datetime import datetime


class ParentChildKind(str, enum.Enum):
    biological = "biological"
    adoptive = "adoptive"
    step = "step"
    foster = "foster"
    guardian = "guardian"
    unknown = "unknown"


class ParentChildConfidence(str, enum.Enum):
    confirmed = "confirmed"
    probable = "probable"
    uncertain = "uncertain"
    unknown = "unknown"


class RelationshipSource(str, enum.Enum):
    manual = "manual"
    facebook_import = "facebook_import"
    gedcom_import = "gedcom_import"
    federation = "federation"


class ParentChild(Base):
    __tablename__ = "parent_child"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    parent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    child_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(20), default=ParentChildKind.biological.value)
    confidence: Mapped[str | None] = mapped_column(
        String(20), default=ParentChildConfidence.confirmed.value
    )
    source: Mapped[str] = mapped_column(String(30), default=RelationshipSource.manual.value)
    source_detail: Mapped[str | None] = mapped_column(String(500), default=None)
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)
    start_date: Mapped[str | None] = mapped_column(String(10), default=None)
    end_date: Mapped[str | None] = mapped_column(String(10), default=None)
    created_by: Mapped[str | None] = mapped_column(String(36), default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        UniqueConstraint("parent_id", "child_id", "kind", name="uq_parent_child_kind"),
        CheckConstraint("parent_id != child_id", name="ck_no_self_parent"),
    )

    def __repr__(self) -> str:
        return f"<ParentChild parent={self.parent_id[:8]} child={self.child_id[:8]} kind={self.kind}>"


class PartnershipKind(str, enum.Enum):
    married = "married"
    domestic_partner = "domestic_partner"
    co_parent = "co_parent"
    engaged = "engaged"
    other = "other"


class PartnershipStatus(str, enum.Enum):
    active = "active"
    dissolved = "dissolved"
    widowed = "widowed"
    annulled = "annulled"
    separated = "separated"


class Partnership(Base):
    __tablename__ = "partnerships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    person_a_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    person_b_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(30), default=PartnershipKind.married.value)
    status: Mapped[str] = mapped_column(String(20), default=PartnershipStatus.active.value)
    start_date: Mapped[str | None] = mapped_column(String(10), default=None)
    start_date_precision: Mapped[str | None] = mapped_column(String(20), default=None)
    end_date: Mapped[str | None] = mapped_column(String(10), default=None)
    end_date_precision: Mapped[str | None] = mapped_column(String(20), default=None)
    source: Mapped[str] = mapped_column(String(30), default=RelationshipSource.manual.value)
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)
    created_by: Mapped[str | None] = mapped_column(String(36), default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "person_a_id", "person_b_id", "kind", "start_date",
            name="uq_partnership_pair_kind_date",
        ),
        CheckConstraint("person_a_id != person_b_id", name="ck_no_self_partnership"),
        CheckConstraint("person_a_id < person_b_id", name="ck_canonical_order"),
    )

    def __repr__(self) -> str:
        return f"<Partnership a={self.person_a_id[:8]} b={self.person_b_id[:8]} kind={self.kind}>"
