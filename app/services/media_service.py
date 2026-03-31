"""
Media file processing — save, dedup, extract metadata, resize, thumbnail.

Upload pipeline:
1. Validate MIME type + size
2. SHA-256 dedup check
3. HEIC → JPEG conversion if needed
4. Extract EXIF/video metadata (GPS, date, camera, orientation)
5. Save original file
6. Generate resized variant (2048px max / 720p video)
7. Generate thumbnail (400px)
8. Generate video thumbnail via ffmpeg
9. Create Media record with all metadata
"""

import hashlib
import os
import uuid
from io import BytesIO

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.media import Media, MediaSource, MediaType
from app.services.metadata_service import (
    extract_image_metadata,
    extract_video_metadata,
    generate_video_thumbnail,
    resize_image,
    is_heic,
    convert_heic_to_jpeg,
)

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "image/heic", "image/heif",
    "video/mp4", "video/quicktime", "video/webm",
    "audio/opus", "audio/mp3", "audio/m4a", "audio/ogg",
}

IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif"}

MAX_SIZE_BY_CATEGORY = {
    "image": 30 * 1024 * 1024,      # 30 MB (increased for HEIC raw)
    "video": 500 * 1024 * 1024,     # 500 MB (real vacation videos)
    "audio": 25 * 1024 * 1024,      # 25 MB
}

THUMBNAIL_SIZE = (400, 400)
HIGH_QUALITY_MAX_DIM = 2048  # pixels for "high quality" resized variant


def _category_for_mime(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("audio/"):
        return "audio"
    return "image"


def _media_type_for_mime(mime_type: str) -> str:
    if mime_type == "image/gif":
        return MediaType.gif.value
    if mime_type.startswith("image/"):
        return MediaType.image.value
    if mime_type.startswith("video/"):
        return MediaType.video.value
    if mime_type.startswith("audio/"):
        return MediaType.audio.value
    return MediaType.image.value


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate_thumbnail(data: bytes, mime_type: str) -> bytes | None:
    """Generate a thumbnail for image files."""
    if not mime_type.startswith("image/") or mime_type == "image/gif":
        return None
    try:
        img = Image.open(BytesIO(data))
        # Auto-rotate per EXIF before thumbnailing
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        img.thumbnail(THUMBNAIL_SIZE)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = BytesIO()
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    except Exception:
        return None


async def check_duplicate(db: AsyncSession, file_hash: str) -> Media | None:
    result = await db.execute(select(Media).where(Media.file_hash == file_hash))
    return result.scalar_one_or_none()


async def save_media_file(
    db: AsyncSession,
    file_data: bytes,
    filename: str,
    mime_type: str,
    person_id: str,
    uploaded_by: str,
    caption: str | None = None,
    data_dir: str | None = None,
    source: str = MediaSource.manual.value,
    resize: bool = True,
) -> tuple[Media, bool]:
    """
    Save a media file with full metadata extraction.
    Returns (media, is_duplicate).
    """
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported MIME type: {mime_type}")

    # HEIC conversion
    if is_heic(mime_type, filename):
        result = convert_heic_to_jpeg(file_data)
        if result:
            file_data, mime_type = result
            # Update filename extension
            if filename:
                base = os.path.splitext(filename)[0]
                filename = f"{base}.jpg"
        else:
            raise ValueError("HEIC conversion failed — install pillow-heif or ImageMagick")

    category = _category_for_mime(mime_type)
    max_size = MAX_SIZE_BY_CATEGORY[category]
    if len(file_data) > max_size:
        raise ValueError(f"File too large: {len(file_data)} bytes (max {max_size})")

    file_hash = compute_sha256(file_data)

    existing = await check_duplicate(db, file_hash)
    if existing:
        return existing, True

    if data_dir is None:
        data_dir = get_settings().DATA_DIR

    media_id = str(uuid.uuid4())
    ext = os.path.splitext(filename)[1].lower() if filename else ""
    relative_path = f"{media_id}{ext}"

    media_dir = os.path.join(data_dir, "media")
    os.makedirs(media_dir, exist_ok=True)

    file_path = os.path.join(media_dir, relative_path)

    # ─── Extract metadata BEFORE stripping EXIF ───────────────
    meta = None
    if mime_type.startswith("image/"):
        meta = extract_image_metadata(file_data, filename)
    # Video metadata extracted after saving (needs file on disk for ffprobe)

    # ─── Save original ────────────────────────────────────────
    with open(file_path, "wb") as f:
        f.write(file_data)

    # ─── Video metadata + thumbnail ───────────────────────────
    video_thumb_relative = None
    if mime_type.startswith("video/"):
        meta = extract_video_metadata(file_path, filename)
        # Generate video thumbnail
        thumb_dir = os.path.join(media_dir, "thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, f"{media_id}.jpg")
        if generate_video_thumbnail(file_path, thumb_path):
            video_thumb_relative = f"thumbnails/{media_id}.jpg"

    # ─── Image thumbnail ─────────────────────────────────────
    if mime_type.startswith("image/") and mime_type != "image/gif":
        thumb_data = generate_thumbnail(file_data, mime_type)
        if thumb_data:
            thumb_dir = os.path.join(media_dir, "thumbnails")
            os.makedirs(thumb_dir, exist_ok=True)
            thumb_path = os.path.join(thumb_dir, f"{media_id}.jpg")
            with open(thumb_path, "wb") as f:
                f.write(thumb_data)

    # ─── Resized variant ──────────────────────────────────────
    resized_path_relative = None
    resized_w = None
    resized_h = None
    resized_size = None

    if resize and mime_type.startswith("image/") and mime_type != "image/gif":
        resized = resize_image(file_data, max_dimension=HIGH_QUALITY_MAX_DIM)
        if resized:
            resized_bytes, resized_w, resized_h = resized
            resized_path_relative = f"resized/{media_id}.jpg"
            resized_dir = os.path.join(media_dir, "resized")
            os.makedirs(resized_dir, exist_ok=True)
            resized_full = os.path.join(resized_dir, f"{media_id}.jpg")
            with open(resized_full, "wb") as f:
                f.write(resized_bytes)
            resized_size = len(resized_bytes)

    # ─── Build Media record ───────────────────────────────────
    width = meta.width if meta else None
    height = meta.height if meta else None

    # Fallback dimensions for images without EXIF
    if width is None and mime_type.startswith("image/"):
        try:
            img = Image.open(BytesIO(file_data))
            width, height = img.width, img.height
        except Exception:
            pass

    media = Media(
        id=media_id,
        person_id=person_id,
        file_path=relative_path,
        original_filename=filename,
        media_type=_media_type_for_mime(mime_type),
        mime_type=mime_type,
        width=width,
        height=height,
        duration_seconds=meta.duration_seconds if meta else None,
        file_size_bytes=len(file_data),
        file_hash=file_hash,
        caption=caption,
        source=source,
        uploaded_by=uploaded_by,
        # EXIF / metadata
        taken_date=meta.taken_date if meta else None,
        taken_at=meta.taken_at if meta else None,
        taken_at_source=meta.taken_at_source if meta else None,
        location_lat=meta.location_lat if meta else None,
        location_lng=meta.location_lng if meta else None,
        location_alt=meta.location_alt if meta else None,
        camera_make=meta.camera_make if meta else None,
        camera_model=meta.camera_model if meta else None,
        orientation=meta.orientation if meta else None,
        has_exif=meta.has_exif if meta else None,
        video_codec=meta.video_codec if meta else None,
        video_thumbnail_path=video_thumb_relative,
        # Resized
        resized_path=resized_path_relative,
        resized_width=resized_w,
        resized_height=resized_h,
        resized_size_bytes=resized_size,
    )
    db.add(media)
    await db.flush()

    return media, False
