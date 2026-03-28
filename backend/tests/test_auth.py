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
    assert "access_token" in body
    assert body["role"] == "teacher"
    assert "user_id" in body
    assert body["name"] == "T"


@pytest.mark.asyncio
async def test_login_invalid(client: AsyncClient, seed_school: School):
    res = await client.post("/api/v1/auth/login", json={"email": "no@test.com", "password": "pw"})
    assert res.status_code == 401
    assert res.json()["code"] == "AUTH_INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, seed_school: School):
    async with async_session_test() as session:
        user = User(
            school_id=seed_school.id,
            email="wp@test.com",
            hashed_password=hash_password("correct"),
            role="teacher",
            name="WP",
        )
        session.add(user)
        await session.commit()

    res = await client.post("/api/v1/auth/login", json={"email": "wp@test.com", "password": "wrong"})
    assert res.status_code == 401
    assert res.json()["code"] == "AUTH_INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_me_requires_auth(auth_client_teacher: AsyncClient):
    res = await auth_client_teacher.get("/api/v1/auth/me")
    assert res.status_code == 200
    assert res.json()["role"] == "teacher"


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    res = await client.get("/api/v1/auth/me")
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_returns_correct_user_info(auth_client_teacher: AsyncClient, seed_teacher):
    res = await auth_client_teacher.get("/api/v1/auth/me")
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == seed_teacher.email
    assert body["name"] == seed_teacher.name
    assert body["role"] == "teacher"
    assert body["school_id"] == str(seed_teacher.school_id)


@pytest.mark.asyncio
async def test_login_inactive_account(client: AsyncClient, seed_school: School):
    async with async_session_test() as session:
        user = User(
            school_id=seed_school.id,
            email="inactive@test.com",
            hashed_password=hash_password("pw"),
            role="teacher",
            name="Inactive",
            is_active=False,
        )
        session.add(user)
        await session.commit()

    res = await client.post("/api/v1/auth/login", json={"email": "inactive@test.com", "password": "pw"})
    assert res.status_code == 401
    assert res.json()["code"] == "AUTH_ACCOUNT_INACTIVE"


@pytest.mark.asyncio
async def test_logout(auth_client_teacher: AsyncClient):
    res = await auth_client_teacher.post("/api/v1/auth/logout")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_refresh_without_cookie(client: AsyncClient):
    res = await client.post("/api/v1/auth/refresh")
    assert res.status_code == 401
    assert res.json()["code"] == "AUTH_TOKEN_EXPIRED"
