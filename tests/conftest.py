import os
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set env vars before any app imports
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-1234567890")
os.environ.setdefault("FERNET_KEY", "dGVzdC1mZXJuZXQta2V5LW5vdC1mb3ItcHJvZHVjdGlvbg==")
os.environ.setdefault("BASE_URL", "http://localhost:8000")
os.environ.setdefault("DATABASE_URL", "sqlite:///data/family.db")

from app.database import get_db
from app.models.base import Base
from app.models.person import Person, PersonSource, AccountState
from app.models.relationships import ParentChild, Partnership
from app.routes.auth_routes import router as auth_router
from app.routes.health import router as health_router
from app.routes.persons import router as persons_router
from app.routes.relationships import router as relationships_router
from app.routes.tree import router as tree_router
from app.routes.media import router as media_router
from app.routes.moments import router as moments_router
from app.routes.trips import router as trips_router
from app.routes.upload import router as upload_router
from app.services.auth_service import create_session


def _set_sqlite_pragmas(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


@pytest_asyncio.fixture
async def engine():
    """In-memory SQLite engine for tests."""
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    event.listens_for(test_engine.sync_engine, "connect")(_set_sqlite_pragmas)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db(session_factory):
    """Database session for direct test setup and assertions."""
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_db(db: AsyncSession):
    """Database with root person, Alex (admin), and Maria (admin)."""
    root = Person(
        id="root-0000-0000-0000-000000000001",
        first_name="Our",
        last_name="Family",
        is_root=True,
        is_admin=False,
        source=PersonSource.manual.value,
        account_state=AccountState.active.value,
    )
    alex = Person(
        id="alex-000-0000-0000-000000000002",
        first_name="Alex",
        last_name="Rivera",
        gender="male",
        residence_country_code="ES",
        branch="rivera",
        is_admin=True,
        is_root=False,
        contact_email="alex@example.com",
        source=PersonSource.manual.value,
        account_state=AccountState.active.value,
    )
    maria = Person(
        id="maria-00-0000-0000-000000000003",
        first_name="Maria",
        last_name="Santos",
        gender="female",
        residence_country_code="ES",
        branch="maria",
        is_admin=True,
        is_root=False,
        source=PersonSource.manual.value,
        account_state=AccountState.active.value,
    )
    grandpa = Person(
        id="grndpa-00-0000-0000-000000000004",
        first_name="James",
        last_name="Rivera",
        gender="male",
        residence_country_code="CA",
        branch="rivera",
        is_admin=False,
        source=PersonSource.manual.value,
        account_state=AccountState.active.value,
    )
    member = Person(
        id="member-00-0000-0000-000000000005",
        first_name="Jane",
        last_name="Rivera",
        gender="female",
        residence_country_code="CA",
        branch="rivera",
        is_admin=False,
        source=PersonSource.manual.value,
        account_state=AccountState.active.value,
    )
    db.add_all([root, alex, maria, grandpa, member])
    await db.flush()

    # Alex and Maria are parents of root (Mia)
    pc1 = ParentChild(parent_id=alex.id, child_id=root.id, kind="biological")
    pc2 = ParentChild(parent_id=maria.id, child_id=root.id, kind="biological")
    # Grandpa is Alex's parent
    pc3 = ParentChild(parent_id=grandpa.id, child_id=alex.id, kind="biological")
    db.add_all([pc1, pc2, pc3])

    # Alex + Maria partnership (canonical ordering)
    a_id, b_id = sorted([alex.id, maria.id])
    p1 = Partnership(person_a_id=a_id, person_b_id=b_id, kind="married", status="active")
    db.add(p1)

    await db.flush()
    await db.commit()
    yield db


@pytest.fixture
def phase1_app():
    """Phase 1 app assembly, isolated from in-progress Phase 2/3 work in app.main."""
    application = FastAPI(
        title="Family Book",
        description="Private, self-hosted family tree and archive",
        version="0.1.0",
    )
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(persons_router)
    application.include_router(relationships_router)
    application.include_router(tree_router)
    application.include_router(media_router)
    application.include_router(moments_router)
    application.include_router(trips_router)
    application.include_router(upload_router)
    return application


@pytest.fixture
def app_under_test(phase1_app: FastAPI):
    """
    Prefer the live app factory when concurrent Phase 2/3 work is importable.
    Fall back to a Phase 1-only app while app.main is in a partial state.
    """
    try:
        from app.main import create_app
    except Exception:
        return phase1_app
    return create_app()


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.services import site_settings

    site_settings._cache = None
    yield
    site_settings._cache = None


@pytest_asyncio.fixture
async def client(seeded_db: AsyncSession, session_factory, app_under_test: FastAPI):
    """Test client with per-request database sessions."""

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app_under_test.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app_under_test)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app_under_test.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_client(seeded_db: AsyncSession, client: AsyncClient):
    """Test client authenticated as Alex (admin)."""
    token = await create_session(
        seeded_db,
        person_id="alex-000-0000-0000-000000000002",
        auth_method="magic_link",
    )
    await seeded_db.commit()
    client.cookies.set("session", token)
    yield client
    client.cookies.clear()


@pytest_asyncio.fixture
async def member_client(seeded_db: AsyncSession, session_factory, app_under_test: FastAPI):
    """Test client authenticated as Jane (member, not admin) — independent from admin_client."""

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app_under_test.dependency_overrides[get_db] = override_get_db

    token = await create_session(
        seeded_db,
        person_id="member-00-0000-0000-000000000005",
        auth_method="magic_link",
    )
    await seeded_db.commit()

    transport = ASGITransport(app=app_under_test)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.cookies.set("session", token)
        yield ac
