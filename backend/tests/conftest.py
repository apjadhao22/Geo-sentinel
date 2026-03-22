import pytest
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.database import Base
from app.models.user import User
from app.services.auth_service import hash_password

TEST_DATABASE_URL = "postgresql+asyncpg://pcmc:pcmc_dev_password@localhost:5432/pcmc_construction_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
async def override_db(db_session):
    from app.main import app
    from app.database import get_db

    async def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client():
    from httpx import AsyncClient, ASGITransport
    from app.main import app as fastapi_app
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seed_users(db_session):
    users = [
        User(username="officer1", password_hash=hash_password("test123"), full_name="Officer One", role="reviewer"),
        User(username="admin1", password_hash=hash_password("test123"), full_name="Admin One", role="admin"),
        User(username="superadmin", password_hash=hash_password("test123"), full_name="Super Admin", role="super_admin"),
    ]
    for u in users:
        db_session.add(u)
    await db_session.flush()
    return users
