import enum

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid
from datetime import datetime


class MediaType(str, enum.Enum):
    image = "image"
    video = "video"
    audio = "audio"
    sticker = "sticker"
    gif = "gif"
    embed = "embed"


class MediaSource(str, enum.Enum):
    manual = "manual"
    whatsapp_import = "whatsapp_import"
    facebook_import = "facebook_import"
    messenger_import = "messenger_import"
    instagram_import = "instagram_import"
    email = "email"
    share_sheet = "share_sheet"
    telegram = "telegram"
    matrix = "matrix"
    facebook_oauth = "facebook_oauth"


class Media(Base):
    __tablename__ = "media"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.id", ondelete="CASCADE")
    )
    file_path: Mapped[str | None] = mapped_column(String(500), default=None)
    original_filename: Mapped[str | None] = mapped_column(String(300), default=None)
    media_type: Mapped[str] = mapped_column(String(20))
    mime_type: Mapped[str | None] = mapped_column(String(50), default=None)
    width: Mapped[int | None] = mapped_column(Integer, default=None)
    height: Mapped[int | None] = mapped_column(Integer, default=None)
    duration_seconds: Mapped[float | None] = mapped_column(Float, default=None)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, default=None)
    file_hash: Mapped[str | None] = mapped_column(String(64), default=None)  # SHA-256
    embed_url: Mapped[str | None] = mapped_column(String(2000), default=None)
    embed_provider: Mapped[str | None] = mapped_column(String(50), default=None)
    embed_html: Mapped[str | None] = mapped_column(Text, default=None)
    caption: Mapped[str | None] = mapped_column(String(1000), default=None)
    taken_date: Mapped[str | None] = mapped_column(String(10), default=None)
    source: Mapped[str] = mapped_column(String(30), default=MediaSource.manual.value)
    is_profile: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_by: Mapped[str | None] = mapped_column(String(36), default=None)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<Media id={self.id[:8]} type={self.media_type}>"
