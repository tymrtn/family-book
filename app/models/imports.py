import enum
import json

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_uuid, utcnow
from datetime import datetime


class ImportStatus(str, enum.Enum):
    pending = "pending"
    parsing = "parsing"
    mapping = "mapping"
    importing = "importing"
    paused = "paused"
    completed = "completed"
    failed = "failed"


class WhatsappImportBatch(Base):
    __tablename__ = "whatsapp_import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    filename: Mapped[str] = mapped_column(String(300))
    raw_content_path: Mapped[str] = mapped_column(String(500))
    date_format: Mapped[str | None] = mapped_column(String(50), default=None)
    group_name: Mapped[str | None] = mapped_column(String(300), default=None)
    status: Mapped[str] = mapped_column(String(20), default=ImportStatus.pending.value)
    _stats: Mapped[str | None] = mapped_column("stats", Text, default="{}")
    _sender_mappings: Mapped[str | None] = mapped_column("sender_mappings", Text, default="{}")
    imported_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)

    @property
    def stats(self) -> dict:
        return json.loads(self._stats) if self._stats else {}

    @stats.setter
    def stats(self, value: dict) -> None:
        self._stats = json.dumps(value)

    @property
    def sender_mappings(self) -> dict:
        return json.loads(self._sender_mappings) if self._sender_mappings else {}

    @sender_mappings.setter
    def sender_mappings(self, value: dict) -> None:
        self._sender_mappings = json.dumps(value)


class MessengerImportBatch(Base):
    __tablename__ = "messenger_import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    filename: Mapped[str] = mapped_column(String(300))
    raw_content_path: Mapped[str] = mapped_column(String(500))
    group_name: Mapped[str | None] = mapped_column(String(300), default=None)
    status: Mapped[str] = mapped_column(String(20), default=ImportStatus.pending.value)
    _stats: Mapped[str | None] = mapped_column("stats", Text, default="{}")
    _sender_mappings: Mapped[str | None] = mapped_column("sender_mappings", Text, default="{}")
    imported_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)

    @property
    def stats(self) -> dict:
        return json.loads(self._stats) if self._stats else {}

    @stats.setter
    def stats(self, value: dict) -> None:
        self._stats = json.dumps(value)

    @property
    def sender_mappings(self) -> dict:
        return json.loads(self._sender_mappings) if self._sender_mappings else {}

    @sender_mappings.setter
    def sender_mappings(self, value: dict) -> None:
        self._sender_mappings = json.dumps(value)


class AgentApiKey(Base):
    __tablename__ = "agent_api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(200))
    key_hash: Mapped[str] = mapped_column(String(64))
    key_prefix: Mapped[str] = mapped_column(String(8))
    scope: Mapped[str] = mapped_column(String(20))
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    created_by: Mapped[str] = mapped_column(String(36))
    last_used: Mapped[datetime | None] = mapped_column(default=None)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ExternalIdentity(Base):
    __tablename__ = "external_identities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str] = mapped_column(String(500))
    _metadata: Mapped[str | None] = mapped_column("metadata", Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        __import__("sqlalchemy").UniqueConstraint(
            "provider", "external_id", name="uq_external_identity"
        ),
    )


class MemorialPlan(Base):
    __tablename__ = "memorial_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE"), unique=True
    )
    memorial_photo_id: Mapped[str | None] = mapped_column(String(36), default=None)
    memorial_bio: Mapped[str | None] = mapped_column(Text, default=None)
    memorial_message: Mapped[str | None] = mapped_column(Text, default=None)
    memorial_music_url: Mapped[str | None] = mapped_column(String(2000), default=None)
    memorial_wishes: Mapped[str | None] = mapped_column(String(2000), default=None)
    contact_visible_after_death: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
