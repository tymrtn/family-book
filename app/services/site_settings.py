import json
from asyncio import Lock
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import get_settings


DEFAULT_ACCENT = "forest"
ACCENT_PRESETS = {"forest", "ocean", "rose"}
SITE_STATE_UNCLAIMED = "unclaimed"
SITE_STATE_CLAIMED = "claimed"


@dataclass
class SiteSettings:
    title: Optional[str] = None
    accent: str = DEFAULT_ACCENT
    state: str = SITE_STATE_UNCLAIMED
    claimed_at: Optional[str] = None
    claimed_by: Optional[str] = None


_cache: SiteSettings | None = None
claim_lock = Lock()


def _settings_path() -> Path:
    settings = get_settings()
    path = Path(settings.DATA_DIR) / "site_settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _legacy_settings_path() -> Path:
    settings = get_settings()
    return Path(settings.DATA_DIR) / "site.json"


def _normalize_settings(data: dict) -> SiteSettings:
    title = data.get("title") or None
    accent = data.get("accent") or DEFAULT_ACCENT
    if accent not in ACCENT_PRESETS:
        accent = DEFAULT_ACCENT
    state = data.get("state") or data.get("site_state") or SITE_STATE_UNCLAIMED
    if state not in {SITE_STATE_UNCLAIMED, SITE_STATE_CLAIMED}:
        state = SITE_STATE_UNCLAIMED
    return SiteSettings(
        title=title,
        accent=accent,
        state=state,
        claimed_at=data.get("claimed_at") or None,
        claimed_by=data.get("claimed_by") or None,
    )


def get_site_settings(force_reload: bool = False) -> SiteSettings:
    global _cache
    if _cache and not force_reload:
        return _cache

    for path in (_settings_path(), _legacy_settings_path()):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            _cache = _normalize_settings(data)
            return _cache
        except Exception:
            continue

    _cache = SiteSettings()
    return _cache


def save_site_settings(
    title: Optional[str],
    accent: str | None = None,
    *,
    state: str | None = None,
    claimed_at: str | None = None,
    claimed_by: str | None = None,
) -> SiteSettings:
    existing = get_site_settings()
    clean_title = (title or "").strip() or None
    clean_accent = accent if accent in ACCENT_PRESETS else existing.accent
    clean_state = state if state in {SITE_STATE_UNCLAIMED, SITE_STATE_CLAIMED} else existing.state

    settings = SiteSettings(
        title=clean_title,
        accent=clean_accent,
        state=clean_state,
        claimed_at=claimed_at if claimed_at is not None else existing.claimed_at,
        claimed_by=claimed_by if claimed_by is not None else existing.claimed_by,
    )
    path = _settings_path()
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")

    global _cache
    _cache = settings
    return settings


def claim_site(*, title: Optional[str], claimed_by: str) -> SiteSettings:
    return save_site_settings(
        title,
        state=SITE_STATE_CLAIMED,
        claimed_at=datetime.now(timezone.utc).isoformat(),
        claimed_by=claimed_by,
    )


def is_site_claimed(force_reload: bool = False) -> bool:
    return get_site_settings(force_reload=force_reload).state == SITE_STATE_CLAIMED
