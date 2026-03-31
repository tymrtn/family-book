"""
EXIF and video metadata extraction.

Extracts GPS, DateTimeOriginal, camera info, orientation from images.
Extracts creation_time, GPS, duration, resolution, codec from video.
Detects forwarded media (no EXIF = likely WhatsApp/Telegram forward).
Falls back to filename date patterns (IMG_20260331_1523.jpg).
"""

import re
import subprocess
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


@dataclass
class MediaMetadata:
    """Extracted metadata from a media file."""
    # Location
    location_lat: float | None = None
    location_lng: float | None = None
    location_alt: float | None = None

    # Timestamp
    taken_at: datetime | None = None
    taken_at_source: str | None = None  # exif, filename, manual, approximate
    taken_date: str | None = None       # ISO date string for backward compat

    # Camera
    camera_make: str | None = None
    camera_model: str | None = None
    orientation: int | None = None

    # Image dimensions (after orientation correction)
    width: int | None = None
    height: int | None = None

    # EXIF presence
    has_exif: bool = False

    # Video-specific
    duration_seconds: float | None = None
    video_codec: str | None = None


# ─── EXIF GPS Helpers ─────────────────────────────────────────────

def _gps_to_decimal(gps_coords, gps_ref) -> float | None:
    """Convert GPS DMS (degrees, minutes, seconds) to decimal degrees."""
    try:
        degrees = float(gps_coords[0])
        minutes = float(gps_coords[1])
        seconds = float(gps_coords[2])
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        if gps_ref in ('S', 'W'):
            decimal = -decimal
        return round(decimal, 7)
    except (TypeError, ValueError, IndexError, ZeroDivisionError):
        return None


def _parse_exif_datetime(dt_str: str) -> datetime | None:
    """Parse EXIF datetime string (YYYY:MM:DD HH:MM:SS)."""
    if not dt_str or not isinstance(dt_str, str):
        return None
    # EXIF uses colons in date: "2026:03:31 15:23:45"
    dt_str = dt_str.strip().replace('\x00', '')
    if not dt_str:
        return None
    for fmt in (
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y:%m:%d",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# ─── Filename Date Extraction ─────────────────────────────────────

# Common patterns: IMG_20260331_152345.jpg, VID_20260331_152345.mp4,
# Screenshot_2026-03-31-15-23-45.png, PXL_20260331_152345678.jpg,
# WhatsApp Image 2026-03-31 at 15.23.45.jpeg
_FILENAME_DATE_PATTERNS = [
    # IMG_20260331_152345 or VID_20260331_152345
    re.compile(r'(?:IMG|VID|PXL|MVIMG|BURST|DSC|DSCN|P|PANO)_?(\d{8})_?(\d{6})', re.IGNORECASE),
    # Screenshot_2026-03-31-15-23-45
    re.compile(r'(\d{4})-(\d{2})-(\d{2})[_\-](\d{2})[_\-.](\d{2})[_\-.](\d{2})'),
    # WhatsApp Image 2026-03-31 at 15.23.45
    re.compile(r'(\d{4})-(\d{2})-(\d{2})\s+at\s+(\d{2})\.(\d{2})\.(\d{2})'),
    # Just a date: 20260331
    re.compile(r'(\d{4})(\d{2})(\d{2})'),
]


def _parse_date_from_filename(filename: str) -> datetime | None:
    """Try to extract a date from the filename."""
    if not filename:
        return None

    name = os.path.splitext(filename)[0]

    # Pattern 1: IMG_20260331_152345
    m = _FILENAME_DATE_PATTERNS[0].search(name)
    if m:
        date_str = m.group(1)
        time_str = m.group(2)
        try:
            return datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    # Pattern 2: Screenshot_2026-03-31-15-23-45
    m = _FILENAME_DATE_PATTERNS[1].search(name)
    if m:
        try:
            return datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)), int(m.group(6)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass

    # Pattern 3: WhatsApp Image 2026-03-31 at 15.23.45
    m = _FILENAME_DATE_PATTERNS[2].search(name)
    if m:
        try:
            return datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)), int(m.group(6)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass

    # Pattern 4: Just date 20260331
    m = _FILENAME_DATE_PATTERNS[3].search(name)
    if m:
        try:
            dt = datetime.strptime(f"{m.group(1)}{m.group(2)}{m.group(3)}", "%Y%m%d")
            # Validate reasonable year range
            if 1990 <= dt.year <= 2050:
                return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


# ─── Image EXIF Extraction ────────────────────────────────────────

def extract_image_metadata(file_data: bytes, filename: str | None = None) -> MediaMetadata:
    """Extract EXIF metadata from an image file."""
    meta = MediaMetadata()

    try:
        img = Image.open(BytesIO(file_data))
        meta.width = img.width
        meta.height = img.height
    except Exception:
        return meta

    try:
        exif_data = img._getexif()
    except (AttributeError, Exception):
        exif_data = None

    if not exif_data:
        meta.has_exif = False
        # Fall back to filename date
        if filename:
            fn_date = _parse_date_from_filename(filename)
            if fn_date:
                meta.taken_at = fn_date
                meta.taken_at_source = "filename"
                meta.taken_date = fn_date.strftime("%Y-%m-%d")
        return meta

    meta.has_exif = True
    decoded = {}
    for tag_id, value in exif_data.items():
        tag_name = TAGS.get(tag_id, str(tag_id))
        decoded[tag_name] = value

    # DateTime — prefer DateTimeOriginal > DateTimeDigitized > DateTime
    for dt_tag in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
        if dt_tag in decoded:
            dt = _parse_exif_datetime(str(decoded[dt_tag]))
            if dt:
                meta.taken_at = dt
                meta.taken_at_source = "exif"
                meta.taken_date = dt.strftime("%Y-%m-%d")
                break

    # Camera
    if "Make" in decoded:
        meta.camera_make = str(decoded["Make"]).strip().rstrip('\x00')
    if "Model" in decoded:
        meta.camera_model = str(decoded["Model"]).strip().rstrip('\x00')

    # Orientation
    if "Orientation" in decoded:
        try:
            meta.orientation = int(decoded["Orientation"])
            # Correct width/height for rotated images
            if meta.orientation in (5, 6, 7, 8):
                meta.width, meta.height = meta.height, meta.width
        except (ValueError, TypeError):
            pass

    # GPS
    if "GPSInfo" in decoded:
        gps_info = decoded["GPSInfo"]
        gps_decoded = {}
        for key, val in gps_info.items():
            gps_tag = GPSTAGS.get(key, str(key))
            gps_decoded[gps_tag] = val

        if "GPSLatitude" in gps_decoded and "GPSLatitudeRef" in gps_decoded:
            meta.location_lat = _gps_to_decimal(
                gps_decoded["GPSLatitude"],
                gps_decoded["GPSLatitudeRef"],
            )
        if "GPSLongitude" in gps_decoded and "GPSLongitudeRef" in gps_decoded:
            meta.location_lng = _gps_to_decimal(
                gps_decoded["GPSLongitude"],
                gps_decoded["GPSLongitudeRef"],
            )
        if "GPSAltitude" in gps_decoded:
            try:
                alt = float(gps_decoded["GPSAltitude"])
                ref = gps_decoded.get("GPSAltitudeRef", 0)
                meta.location_alt = -alt if ref == 1 else alt
            except (TypeError, ValueError):
                pass

    # Fall back to filename if no EXIF datetime found
    if not meta.taken_at and filename:
        fn_date = _parse_date_from_filename(filename)
        if fn_date:
            meta.taken_at = fn_date
            meta.taken_at_source = "filename"
            meta.taken_date = fn_date.strftime("%Y-%m-%d")

    return meta


# ─── Video Metadata Extraction (via ffprobe) ─────────────────────

def extract_video_metadata(file_path: str, filename: str | None = None) -> MediaMetadata:
    """Extract metadata from a video file using ffprobe."""
    meta = MediaMetadata()

    if not os.path.isfile(file_path):
        return meta

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                file_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return meta

        import json
        probe = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        # ffprobe not available — extract what we can from filename
        if filename:
            fn_date = _parse_date_from_filename(filename)
            if fn_date:
                meta.taken_at = fn_date
                meta.taken_at_source = "filename"
                meta.taken_date = fn_date.strftime("%Y-%m-%d")
        return meta

    # Duration
    fmt = probe.get("format", {})
    if "duration" in fmt:
        try:
            meta.duration_seconds = round(float(fmt["duration"]), 2)
        except ValueError:
            pass

    # Find video stream
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            meta.video_codec = stream.get("codec_name")
            try:
                meta.width = int(stream.get("width", 0)) or None
                meta.height = int(stream.get("height", 0)) or None
            except (ValueError, TypeError):
                pass
            # Check rotation for dimensions
            rotation = 0
            side_data = stream.get("side_data_list", [])
            for sd in side_data:
                if "rotation" in sd:
                    try:
                        rotation = abs(int(sd["rotation"]))
                    except (ValueError, TypeError):
                        pass
            if rotation in (90, 270) and meta.width and meta.height:
                meta.width, meta.height = meta.height, meta.width
            break

    # Creation time from format tags
    tags = fmt.get("tags", {})
    for key in ("creation_time", "com.apple.quicktime.creationdate", "date"):
        if key in tags:
            dt_str = tags[key]
            # ISO format: "2026-03-31T15:23:45.000000Z"
            for fmt_str in (
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S",
            ):
                try:
                    meta.taken_at = datetime.strptime(dt_str, fmt_str)
                    if meta.taken_at.tzinfo is None:
                        meta.taken_at = meta.taken_at.replace(tzinfo=timezone.utc)
                    meta.taken_at_source = "exif"
                    meta.taken_date = meta.taken_at.strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue
            if meta.taken_at:
                break

    # GPS from format tags (some MP4s store it)
    for key in ("com.apple.quicktime.location.ISO6709", "location"):
        if key in tags:
            loc_str = tags[key]
            # ISO6709: "+40.4168-003.7038+667/"
            m = re.match(r'([+-]\d+\.\d+)([+-]\d+\.\d+)', loc_str)
            if m:
                try:
                    meta.location_lat = round(float(m.group(1)), 7)
                    meta.location_lng = round(float(m.group(2)), 7)
                except ValueError:
                    pass

    meta.has_exif = meta.taken_at is not None or meta.location_lat is not None

    # Filename fallback
    if not meta.taken_at and filename:
        fn_date = _parse_date_from_filename(filename)
        if fn_date:
            meta.taken_at = fn_date
            meta.taken_at_source = "filename"
            meta.taken_date = fn_date.strftime("%Y-%m-%d")

    return meta


# ─── Video Thumbnail Generation ──────────────────────────────────

def generate_video_thumbnail(video_path: str, output_path: str) -> bool:
    """Generate a thumbnail from a video at the 1-second mark using ffmpeg."""
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", video_path,
                "-ss", "1", "-vframes", "1",
                "-vf", "scale=400:-1",
                "-q:v", "5",
                output_path,
            ],
            capture_output=True, timeout=30,
        )
        return result.returncode == 0 and os.path.isfile(output_path)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# ─── Image Resize ─────────────────────────────────────────────────

def resize_image(
    file_data: bytes,
    max_dimension: int = 2048,
    quality: int = 85,
) -> tuple[bytes, int, int] | None:
    """
    Resize an image to fit within max_dimension, preserving aspect ratio.
    Returns (resized_bytes, width, height) or None if already small enough.
    """
    try:
        img = Image.open(BytesIO(file_data))
        w, h = img.size
        if w <= max_dimension and h <= max_dimension:
            return None  # Already fits

        # Auto-rotate per EXIF orientation before resize
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        buf = BytesIO()
        # Save as JPEG for universal compat
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue(), img.width, img.height
    except Exception:
        return None


# ─── HEIC Detection & Conversion ─────────────────────────────────

def is_heic(mime_type: str | None, filename: str | None) -> bool:
    """Detect HEIC/HEIF files."""
    if mime_type and mime_type.lower() in ("image/heic", "image/heif"):
        return True
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        return ext in (".heic", ".heif")
    return False


def convert_heic_to_jpeg(file_data: bytes) -> tuple[bytes, str] | None:
    """
    Convert HEIC to JPEG. Returns (jpeg_bytes, 'image/jpeg') or None if failed.
    Requires pillow-heif or Wand installed.
    """
    try:
        # Try pillow-heif first (most common)
        import pillow_heif
        heif_file = pillow_heif.read_heif(file_data)
        img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw")
        buf = BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=92)
        return buf.getvalue(), "image/jpeg"
    except ImportError:
        pass
    except Exception:
        pass

    try:
        # Fallback: use ImageMagick via subprocess
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as f:
            f.write(file_data)
            heic_path = f.name
        jpeg_path = heic_path.replace(".heic", ".jpg")
        result = subprocess.run(
            ["convert", heic_path, jpeg_path],
            capture_output=True, timeout=30,
        )
        try:
            os.unlink(heic_path)
        except OSError:
            pass
        if result.returncode == 0 and os.path.isfile(jpeg_path):
            with open(jpeg_path, "rb") as f:
                data = f.read()
            try:
                os.unlink(jpeg_path)
            except OSError:
                pass
            return data, "image/jpeg"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None
