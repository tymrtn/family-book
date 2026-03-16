import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import event

from app.models.base import Base
from app.models.person import Person, PersonSource, AccountState
from app.models.relationships import ParentChild, Partnership
from app.models.auth import UserSession
from app.services.auth_service import create_session

# Set env vars before any app imports
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-1234567890")
os.environ.setdefault("FERNET_KEY", "dGVzdC1mZXJuZXQta2V5LW5vdC1mb3ItcHJvZHVjdGlvbg==")
os.environ.setdefault("BASE_URL", "http://localhost:8000")
os.environ.setdefault("DATABASE_URL", "sqlite:///data/family.db")


def _set_sqlite_pragmas(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


@pytest_asyncio.fixture
async def db():
    """In-memory SQLite database for tests."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    event.listens_for(engine.sync_engine, "connect")(_set_sqlite_pragmas)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_db(db: AsyncSession):
    """Database with root person, Tyler (admin), and Yuliya (admin)."""
    root = Person(
        id="root-0000-0000-0000-000000000001",
        first_name="Our",
        last_name="Family",
        is_root=True,
        is_admin=False,
        source=PersonSource.manual.value,
        account_state=AccountState.active.value,
    )
    tyler = Person(
        id="tyler-000-0000-0000-000000000002",
        first_name="Tyler",
        last_name="Martin",
        gender="male",
        residence_country_code="ES",
        branch="martin",
        is_admin=True,
        is_root=False,
        contact_email="tyler@example.com",
        source=PersonSource.manual.value,
        account_state=AccountState.active.value,
    )
    yuliya = Person(
        id="yuliya-00-0000-0000-000000000003",
        first_name="Yuliya",
        last_name="Semesock",
        gender="female",
        residence_country_code="ES",
        branch="yuliya",
        is_admin=True,
        is_root=False,
        source=PersonSource.manual.value,
        account_state=AccountState.active.value,
    )
    grandpa = Person(
        id="grndpa-00-0000-0000-000000000004",
        first_name="Robert",
        last_name="Martin",
        gender="male",
        residence_country_code="CA",
        branch="martin",
        is_admin=False,
        source=PersonSource.manual.value,
        account_state=AccountState.active.value,
    )
    member = Person(
        id="member-00-0000-0000-000000000005",
        first_name="Jane",
        last_name="Martin",
        gender="female",
        residence_country_code="CA",
        branch="martin",
        is_admin=False,
        source=PersonSource.manual.value,
        account_state=AccountState.active.value,
    )
    db.add_all([root, tyler, yuliya, grandpa, member])
    await db.flush()

    # Tyler and Yuliya are parents of root (Luna)
    pc1 = ParentChild(parent_id=tyler.id, child_id=root.id, kind="biological")
    pc2 = ParentChild(parent_id=yuliya.id, child_id=root.id, kind="biological")
    # Grandpa is Tyler's parent
    pc3 = ParentChild(parent_id=grandpa.id, child_id=tyler.id, kind="biological")
    db.add_all([pc1, pc2, pc3])

    # Tyler + Yuliya partnership (canonical ordering)
    a_id, b_id = sorted([tyler.id, yuliya.id])
    p1 = Partnership(person_a_id=a_id, person_b_id=b_id, kind="married", status="active")
    db.add(p1)

    await db.flush()
    await db.commit()
    yield db


@pytest_asyncio.fixture
async def client(seeded_db: AsyncSession):
    """Test client with auth dependency overridden."""
    from app.main import app
    from app.database import get_db

    async def override_get_db():
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_client(seeded_db: AsyncSession, client: AsyncClient):
    """Test client authenticated as Tyler (admin)."""
    token = await create_session(
        seeded_db,
        person_id="tyler-000-0000-0000-000000000002",
        auth_method="magic_link",
    )
    await seeded_db.commit()
    client.cookies.set("session", token)
    yield client
    client.cookies.clear()


@pytest_asyncio.fixture
async def member_client(seeded_db: AsyncSession, client: AsyncClient):
    """Test client authenticated as Jane (member, not admin)."""
    token = await create_session(
        seeded_db,
        person_id="member-00-0000-0000-000000000005",
        auth_method="magic_link",
    )
    await seeded_db.commit()
    client.cookies.set("session", token)
    yield client
    client.cookies.clear()
