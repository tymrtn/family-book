import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routes.health import router as health_router
from app.routes.auth_routes import router as auth_router
from app.routes.persons import router as persons_router
from app.routes.relationships import router as relationships_router
from app.routes.tree import router as tree_router
from app.routes.media import router as media_router
from app.routes.moments import router as moments_router
from app.routes.trips import router as trips_router
from app.routes.upload import router as upload_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    data_dir = settings.DATA_DIR
    os.makedirs(os.path.join(data_dir, "media"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "backups"), exist_ok=True)

    # Start Matrix bot if configured
    from app.matrix.startup import start_matrix_bot, stop_matrix_bot
    await start_matrix_bot()

    # Start backup scheduler
    from app.backup.scheduler import start_backup_scheduler, stop_backup_scheduler
    start_backup_scheduler()

    yield

    # Graceful shutdown
    await stop_matrix_bot()
    stop_backup_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Family Book",
        description="Private, self-hosted family tree and archive",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Phase 1 routes
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(persons_router)
    application.include_router(relationships_router)
    application.include_router(tree_router)
    application.include_router(media_router)
    application.include_router(moments_router)
    application.include_router(trips_router)
    application.include_router(upload_router)

    # HTML page routes (HTMX frontend)
    from app.routes.pages import router as pages_router
    application.include_router(pages_router)

    # Phase 3 routes (infrastructure)
    from app.backup.routes import router as backup_router
    from app.inbound.routes import router as inbound_router
    from app.pwa.routes import router as pwa_router
    application.include_router(backup_router)
    application.include_router(inbound_router)
    application.include_router(pwa_router)

    # Demo mode — read-only walkthrough, no auth required
    from app.routes.demo import router as demo_router
    application.include_router(demo_router)

    # 401 handler: redirect to /login for page routes, JSON for API routes
    _API_PREFIXES = ("/api/", "/auth/", "/health", "/invite/")

    @application.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        path = request.url.path
        is_api = any(path.startswith(p) for p in _API_PREFIXES)
        if exc.status_code == 401 and not is_api:
            return RedirectResponse(f"/login?return_to={path}", status_code=302)
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    # Security middleware
    from app.middleware.security import add_security_middleware
    add_security_middleware(application)

    # i18n setup
    from app.i18n import load_translations
    load_translations()

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        application.mount("/static", StaticFiles(directory=static_dir), name="static")

    return application


app = create_app()
