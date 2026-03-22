import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.dependencies.db import get_db
from app.models import School, User
from app.utils.security import hash_password, create_access_token
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_test = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    # Ensure models are registered before creating tables
    import app.models  # noqa: F401
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_test() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seed_school(setup_db) -> School:
    async with async_session_test() as session:
        school = School(name="Test School")
        session.add(school)
        await session.commit()
        await session.refresh(school)
        return school


@pytest.fixture
async def seed_teacher(seed_school) -> User:
    async with async_session_test() as session:
        teacher = User(
            school_id=seed_school.id,
            email="teacher@test.com",
            hashed_password=hash_password("password123"),
            role="teacher",
            name="김교사",
        )
        session.add(teacher)
        await session.commit()
        await session.refresh(teacher)
        return teacher


@pytest.fixture
async def seed_teacher_other(seed_school) -> User:
    async with async_session_test() as session:
        teacher = User(
            school_id=seed_school.id,
            email="teacher2@test.com",
            hashed_password=hash_password("password123"),
            role="teacher",
            name="이교사",
        )
        session.add(teacher)
        await session.commit()
        await session.refresh(teacher)
        return teacher


@pytest.fixture
async def auth_client_teacher(seed_teacher: User) -> AsyncGenerator[AsyncClient, None]:
    token = create_access_token({
        "sub": str(seed_teacher.id),
        "role": seed_teacher.role,
        "school_id": str(seed_teacher.school_id),
    })
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as c:
        yield c


@pytest.fixture
async def auth_client_teacher_other(seed_teacher_other: User) -> AsyncGenerator[AsyncClient, None]:
    token = create_access_token({
        "sub": str(seed_teacher_other.id),
        "role": seed_teacher_other.role,
        "school_id": str(seed_teacher_other.school_id),
    })
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as c:
        yield c
