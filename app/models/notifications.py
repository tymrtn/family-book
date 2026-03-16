import enum

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid, utcnow
from datetime import datetime


class NotificationKind(str, enum.Enum):
    new_moment = "new_moment"
    birthday = "birthday"
    anniversary = "anniversary"
    memorial_anniversary = "memorial_anniversary"
    digest = "digest"
    milestone = "milestone"
    system = "system"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    recipient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(30))
    reference_type: Mapped[str | None] = mapped_column(String(20), default=None)
    reference_id: Mapped[str | None] = mapped_column(String(36), default=None)
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str | None] = mapped_column(Text, default=None)
    media_id: Mapped[str | None] = mapped_column(String(36), default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class DeliveryChannel(str, enum.Enum):
    mms = "mms"
    whatsapp = "whatsapp"
    telegram = "telegram"
    signal = "signal"
    email = "email"
    matrix = "matrix"


class DeliveryStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"
    bounced = "bounced"


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    notification_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notifications.id", ondelete="CASCADE")
    )
    channel: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=DeliveryStatus.pending.value)
    external_id: Mapped[str | None] = mapped_column(String(500), default=None)
    error_message: Mapped[str | None] = mapped_column(String(1000), default=None)
    sent_at: Mapped[datetime | None] = mapped_column(default=None)
    delivered_at: Mapped[datetime | None] = mapped_column(default=None)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class PushChannel(str, enum.Enum):
    auto = "auto"
    whatsapp = "whatsapp"
    telegram = "telegram"
    signal = "signal"
    sms = "sms"
    email = "email"
    none = "none"


class PushFrequency(str, enum.Enum):
    realtime = "realtime"
    daily_digest = "daily_digest"
    weekly_digest = "weekly_digest"


class NotificationPreference(Base, TimestampMixin):
    __tablename__ = "notification_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE"), unique=True
    )
    push_channel: Mapped[str] = mapped_column(String(20), default=PushChannel.auto.value)
    push_phone: Mapped[str | None] = mapped_column(String(20), default=None)
    push_email: Mapped[str | None] = mapped_column(String(320), default=None)
    push_telegram_id: Mapped[str | None] = mapped_column(String(100), default=None)
    push_frequency: Mapped[str] = mapped_column(
        String(20), default=PushFrequency.weekly_digest.value
    )
    push_milestones: Mapped[bool] = mapped_column(Boolean, default=True)
