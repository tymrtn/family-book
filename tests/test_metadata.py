"""Tests for metadata extraction and filename date parsing."""

import pytest
from datetime import datetime, timezone

from app.services.metadata_service import (
    _parse_date_from_filename,
    _parse_exif_datetime,
    _gps_to_decimal,
    extract_image_metadata,
    resize_image,
    is_heic,
    MediaMetadata,
)


class TestFilenameDateParsing:
    def test_img_pattern(self):
        dt = _parse_date_from_filename("IMG_20260331_152345.jpg")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 31
        assert dt.hour == 15
        assert dt.minute == 23

    def test_vid_pattern(self):
        dt = _parse_date_from_filename("VID_20260315_093000.mp4")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 15

    def test_pxl_pattern(self):
        dt = _parse_date_from_filename("PXL_20260401_180000123.jpg")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 4
        assert dt.day == 1

    def test_screenshot_pattern(self):
        dt = _parse_date_from_filename("Screenshot_2026-03-31-15-23-45.png")
        assert dt is not None
        assert dt.year == 2026
        assert dt.hour == 15

    def test_whatsapp_pattern(self):
        dt = _parse_date_from_filename("WhatsApp Image 2026-03-31 at 15.23.45.jpeg")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 31

    def test_no_date(self):
        assert _parse_date_from_filename("photo.jpg") is None

    def test_empty_filename(self):
        assert _parse_date_from_filename("") is None
        assert _parse_date_from_filename(None) is None


class TestExifDateParsing:
    def test_standard_format(self):
        dt = _parse_exif_datetime("2026:03:31 15:23:45")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 31

    def test_iso_format(self):
        dt = _parse_exif_datetime("2026-03-31 15:23:45")
        assert dt is not None
        assert dt.year == 2026

    def test_date_only(self):
        dt = _parse_exif_datetime("2026:03:31")
        assert dt is not None
        assert dt.year == 2026

    def test_invalid(self):
        assert _parse_exif_datetime("not a date") is None
        assert _parse_exif_datetime("") is None
        assert _parse_exif_datetime(None) is None


class TestGPSConversion:
    def test_north_east(self):
        lat = _gps_to_decimal((40, 25, 1.2), "N")
        assert lat is not None
        assert abs(lat - 40.4170) < 0.001

    def test_south_west(self):
        lat = _gps_to_decimal((3, 42, 13.8), "S")
        assert lat is not None
        assert lat < 0

        lng = _gps_to_decimal((3, 42, 13.8), "W")
        assert lng is not None
        assert lng < 0

    def test_invalid(self):
        assert _gps_to_decimal(None, "N") is None
        assert _gps_to_decimal((), "N") is None


class TestImageMetadataExtraction:
    def test_no_exif_image(self):
        """A minimal JPEG with no EXIF should still extract dimensions."""
        from PIL import Image
        from io import BytesIO
        img = Image.new("RGB", (100, 50), color="red")
        buf = BytesIO()
        img.save(buf, format="JPEG")
        data = buf.getvalue()

        meta = extract_image_metadata(data, "test.jpg")
        assert meta.width == 100
        assert meta.height == 50
        assert meta.has_exif is False

    def test_filename_fallback(self):
        """When no EXIF, should fall back to filename date."""
        from PIL import Image
        from io import BytesIO
        img = Image.new("RGB", (100, 50), color="blue")
        buf = BytesIO()
        img.save(buf, format="JPEG")
        data = buf.getvalue()

        meta = extract_image_metadata(data, "IMG_20260715_143000.jpg")
        assert meta.taken_at is not None
        assert meta.taken_at.year == 2026
        assert meta.taken_at.month == 7
        assert meta.taken_at_source == "filename"


class TestImageResize:
    def test_resize_large_image(self):
        from PIL import Image
        from io import BytesIO
        img = Image.new("RGB", (4000, 3000), color="green")
        buf = BytesIO()
        img.save(buf, format="JPEG")
        data = buf.getvalue()

        result = resize_image(data, max_dimension=2048)
        assert result is not None
        resized_bytes, w, h = result
        assert max(w, h) <= 2048
        assert len(resized_bytes) < len(data)

    def test_no_resize_small_image(self):
        from PIL import Image
        from io import BytesIO
        img = Image.new("RGB", (800, 600), color="red")
        buf = BytesIO()
        img.save(buf, format="JPEG")
        data = buf.getvalue()

        result = resize_image(data, max_dimension=2048)
        assert result is None  # Already fits


class TestHEICDetection:
    def test_heic_mime(self):
        assert is_heic("image/heic", None) is True
        assert is_heic("image/heif", None) is True

    def test_heic_extension(self):
        assert is_heic(None, "photo.heic") is True
        assert is_heic(None, "photo.HEIF") is True

    def test_not_heic(self):
        assert is_heic("image/jpeg", "photo.jpg") is False
