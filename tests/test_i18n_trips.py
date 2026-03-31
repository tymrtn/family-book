"""Tests for Trip Albums i18n — locale files, Accept-Language detection."""

import json
import os
import pytest

from app.i18n import t, load_translations

# Ensure translations are loaded
load_translations()


# ─── Locale file completeness ────────────────────────────────────

LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "locales")

REQUIRED_TRIP_KEYS = [
    "trips.title",
    "trips.subtitle",
    "trips.new_trip",
    "trips.create_trip",
    "trips.create_first",
    "trips.no_trips",
    "trips.no_trips_hint",
    "trips.trip_name",
    "trips.trip_name_placeholder",
    "trips.description",
    "trips.description_placeholder",
    "trips.start_date",
    "trips.end_date",
    "trips.creating",
    "trips.contributors",
    "trips.photos",
    "trips.all_trips",
    "trips.tab_timeline",
    "trips.tab_map",
    "trips.tab_contributors",
    "trips.tab_settings",
    "trips.all_days",
    "trips.no_photos",
    "trips.no_photos_hint",
    "trips.loading_map",
    "trips.no_gps",
    "trips.photo_locations",
    "trips.play_trip",
    "trips.stop",
    "trips.invite_contributors",
    "trips.invite_hint",
    "trips.copy",
    "trips.link_copied",
    "trips.new_link",
    "trips.revoke_link",
    "trips.link_refreshed",
    "trips.link_revoked",
    "trips.revoke_confirm",
    "trips.save_changes",
    "trips.trip_updated",
    "trips.export",
    "trips.download_originals",
    "trips.download_high_quality",
    "trips.delete_trip",
    "trips.delete_confirm",
    "trips.add_photos",
    "trips.high_quality",
    "trips.uploading",
    "trips.remaining",
    "trips.upload_done",
    "trips.upload_failed",
    "trips.caption_placeholder",
    "trips.upload",
    "trips.join_title",
    "trips.join_hint",
    "trips.join_button",
    "trips.join_invalid",
    "trips.join_already",
    "trips.join_open",
    "trips.approx_time",
    "trips.by",
    "trips.all_contributors",
    "nav.trips",
]


class TestLocaleCompleteness:
    """Every required trip key exists in en, ru, and es locale files."""

    @pytest.mark.parametrize("locale", ["en", "ru", "es"])
    def test_all_trip_keys_present(self, locale: str):
        path = os.path.join(LOCALES_DIR, f"{locale}.json")
        assert os.path.isfile(path), f"Locale file missing: {path}"

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        missing = []
        for key in REQUIRED_TRIP_KEYS:
            parts = key.split(".")
            current = data
            found = True
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    found = False
                    break
            if not found:
                missing.append(key)

        assert missing == [], f"Missing keys in {locale}.json: {missing}"

    @pytest.mark.parametrize("locale", ["en", "ru", "es"])
    def test_no_empty_values(self, locale: str):
        """No trip translation should be empty string."""
        path = os.path.join(LOCALES_DIR, f"{locale}.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        trips = data.get("trips", {})
        empty = [k for k, v in trips.items() if isinstance(v, str) and v.strip() == ""]
        assert empty == [], f"Empty values in {locale}.json trips: {empty}"


class TestTranslationFunction:
    """The t() function resolves trip keys correctly."""

    def test_english_trip_title(self):
        assert t("trips.title", "en") == "My Trips"

    def test_russian_trip_title(self):
        assert t("trips.title", "ru") == "Мои поездки"

    def test_spanish_trip_title(self):
        assert t("trips.title", "es") == "Mis Viajes"

    def test_russian_add_photos(self):
        """Oleg's Android must see 'Добавить фото и видео'."""
        result = t("trips.add_photos", "ru")
        assert result == "Добавить фото и видео"

    def test_nav_trips_russian(self):
        assert t("nav.trips", "ru") == "Поездки"

    def test_fallback_to_english(self):
        """Unknown locale falls back to English."""
        assert t("trips.title", "zh") == "My Trips"

    def test_unknown_key_returns_key(self):
        """Unknown key returns the key itself."""
        result = t("trips.nonexistent_key_xyz", "en")
        assert result == "trips.nonexistent_key_xyz"


class TestAcceptLanguageDetection:
    """_get_locale parses Accept-Language header correctly."""

    def test_russian_header(self):
        from app.routes.pages import _get_locale
        from unittest.mock import MagicMock

        request = MagicMock()
        request.cookies = {}  # No locale cookie
        request.headers = {"accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"}

        locale = _get_locale(request)
        assert locale == "ru"

    def test_spanish_header(self):
        from app.routes.pages import _get_locale
        from unittest.mock import MagicMock

        request = MagicMock()
        request.cookies = {}
        request.headers = {"accept-language": "es-ES,es;q=0.9,en;q=0.5"}

        locale = _get_locale(request)
        assert locale == "es"

    def test_english_header(self):
        from app.routes.pages import _get_locale
        from unittest.mock import MagicMock

        request = MagicMock()
        request.cookies = {}
        request.headers = {"accept-language": "en-US,en;q=0.9"}

        locale = _get_locale(request)
        assert locale == "en"

    def test_cookie_overrides_header(self):
        """Explicit locale cookie wins over Accept-Language."""
        from app.routes.pages import _get_locale
        from unittest.mock import MagicMock

        request = MagicMock()
        request.cookies = {"locale": "es"}
        request.headers = {"accept-language": "ru-RU,ru;q=0.9"}

        locale = _get_locale(request)
        assert locale == "es"

    def test_unsupported_language_falls_back(self):
        """Japanese header falls back to English."""
        from app.routes.pages import _get_locale
        from unittest.mock import MagicMock

        request = MagicMock()
        request.cookies = {}
        request.headers = {"accept-language": "ja-JP,ja;q=0.9"}

        locale = _get_locale(request)
        assert locale == "en"

    def test_no_header_defaults_english(self):
        from app.routes.pages import _get_locale
        from unittest.mock import MagicMock

        request = MagicMock()
        request.cookies = {}
        request.headers = {}

        locale = _get_locale(request)
        assert locale == "en"

    def test_complex_header_picks_first_supported(self):
        """Header with unsupported first language picks next supported."""
        from app.routes.pages import _get_locale
        from unittest.mock import MagicMock

        request = MagicMock()
        request.cookies = {}
        request.headers = {"accept-language": "de-DE,de;q=0.9,ru;q=0.8,en;q=0.7"}

        locale = _get_locale(request)
        assert locale == "ru"
