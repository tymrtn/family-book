import enum
import json

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_uuid, utcnow
from datetime import datetime


class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"
    merge = "merge"
    import_ = "import"


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    actor_id: Mapped[str | None] = mapped_column(String(36), default=None)
    action: Mapped[str] = mapped_column(String(20))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(36))
    _old_value: Mapped[str | None] = mapped_column("old_value", Text, default=None)
    _new_value: Mapped[str | None] = mapped_column("new_value", Text, default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    @property
    def old_value(self) -> dict | None:
        if self._old_value:
            return json.loads(self._old_value)
        return None

    @old_value.setter
    def old_value(self, value: dict | None) -> None:
        self._old_value = json.dumps(value) if value else None

    @property
    def new_value(self) -> dict | None:
        if self._new_value:
            return json.loads(self._new_value)
        return None

    @new_value.setter
    def new_value(self, value: dict | None) -> None:
        self._new_value = json.dumps(value) if value else None

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.entity_type} {self.entity_id[:8]}>"
