import enum
import json

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_uuid, utcnow
from datetime import datetime


class ApprovalKind(str, enum.Enum):
    minor_photo = "minor_photo"
    memorial_creation = "memorial_creation"
    estrangement = "estrangement"
    readd_ex = "readd_ex"
    visibility_escalation = "visibility_escalation"


class ApprovalThreshold(str, enum.Enum):
    all = "all"
    majority = "majority"
    both_parents = "both_parents"


class ApprovalStatus(str, enum.Enum):
    open = "open"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    kind: Mapped[str] = mapped_column(String(30))
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    initiated_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    reference_type: Mapped[str | None] = mapped_column(String(20), default=None)
    reference_id: Mapped[str | None] = mapped_column(String(36), default=None)
    _required_voters: Mapped[str] = mapped_column("required_voters", Text)
    threshold: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=ApprovalStatus.open.value)
    resolved_at: Mapped[datetime | None] = mapped_column(default=None)
    expires_at: Mapped[datetime] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    @property
    def required_voters(self) -> list[str]:
        return json.loads(self._required_voters)

    @required_voters.setter
    def required_voters(self, value: list[str]) -> None:
        self._required_voters = json.dumps(value)


class VoteChoice(str, enum.Enum):
    approve = "approve"
    reject = "reject"


class ApprovalVote(Base):
    __tablename__ = "approval_votes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("approval_requests.id", ondelete="CASCADE")
    )
    voter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    vote: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        UniqueConstraint("request_id", "voter_id", name="uq_vote_per_voter"),
    )
