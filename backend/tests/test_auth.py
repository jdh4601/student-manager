import pytest
from httpx import AsyncClient

from app.utils.security import hash_password
from tests.conftest import async_session_test
from app.models import User, School


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, seed_school: School):
    async with async_session_test() as session:
        user = User(
            school_id=seed_school.id,
            email="t@test.com",
            hashed_password=hash_password("pw"),
            role="teacher",
            name="T",
        )
        session.add(user)
        await session.commit()

    res = await client.post("/api/v1/auth/login", json={"email": "t@test.com", "password": "pw"})
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body and body["role"] == "teacher"


@pytest.mark.asyncio
async def test_login_invalid(client: AsyncClient, seed_school: School):
    res = await client.post("/api/v1/auth/login", json={"email": "no@test.com", "password": "pw"})
    assert res.status_code == 401
    assert res.json()["code"] == "AUTH_INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_me_requires_auth(auth_client_teacher: AsyncClient):
    res = await auth_client_teacher.get("/api/v1/auth/me")
    assert res.status_code == 200
    assert res.json()["role"] == "teacher"

