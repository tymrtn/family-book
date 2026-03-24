"""
Security middleware — CORS, CSP headers, rate limiting, input sanitization.

Rate limits per SPEC.md:
- /auth/*: 10 req / 15 min per IP
- /api/*:  120 req / 1 min per user
- /api/admin/backup: 2 req / 1 hour
- /invite/*/claim: 5 req / 15 min per IP
"""

import logging
import time
from collections import defaultdict
from contextlib import suppress

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = logging.getLogger(__name__)


def add_security_middleware(app: FastAPI) -> None:
    """Register all security middleware on the app."""
    settings = get_settings()

    # CORS — restrict to same origin in production
    origins = [settings.BASE_URL]
    if "localhost" in settings.BASE_URL:
        origins.append("http://localhost:3000")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Rate limiting
    app.add_middleware(RateLimitMiddleware)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com https://d3js.org; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: blob: https://ui-avatars.com https://picsum.photos https://fastly.picsum.photos; "
            "connect-src 'self'; "
            "font-src 'self' https://fonts.gstatic.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        # Other security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # HSTS in production
        settings = get_settings()
        if settings.BASE_URL.startswith("https://"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter. Not distributed — fine for single-instance."""

    def __init__(self, app):
        super().__init__(app)
        # {key: [(timestamp, ...)]}
        self._windows: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Determine rate limit params
        limit_config = self._get_limit(path)
        if limit_config is None:
            return await call_next(request)

        max_requests, window_seconds, key = limit_config
        key_value = self._resolve_key(request, key)
        bucket = f"{path}:{key_value}"

        now = time.monotonic()
        # Prune old entries
        cutoff = now - window_seconds
        self._windows[bucket] = [t for t in self._windows[bucket] if t > cutoff]

        if len(self._windows[bucket]) >= max_requests:
            logger.warning("Rate limit exceeded: %s (%d/%d)", bucket, len(self._windows[bucket]), max_requests)
            return Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(int(window_seconds))},
            )

        self._windows[bucket].append(now)
        return await call_next(request)

    def _get_limit(self, path: str) -> tuple[int, int, str] | None:
        """Returns (max_requests, window_seconds, key_type) or None."""
        if path.startswith("/auth/") or path.startswith("/api/auth/"):
            return (10, 900, "ip")  # 10/15min per IP
        if "/invite/" in path and path.endswith("/claim"):
            return (5, 900, "ip")  # 5/15min per IP
        if path == "/api/admin/backup":
            return (2, 3600, "ip")  # 2/hour
        if path.startswith("/api/"):
            return (120, 60, "cookie")  # 120/min per user
        return None

    def _resolve_key(self, request: Request, key_type: str) -> str:
        if key_type == "ip":
            return request.client.host if request.client else "unknown"
        if key_type == "cookie":
            return request.cookies.get("session", request.client.host if request.client else "unknown")
        return "global"
