"""교사 Google OAuth 로그인 (REQ-001 보강) — TDD.

데모 범위: 실제 구글 호출 없이 stub provider로 결정론 검증.
보안 핵심: edu 도메인 화이트리스트 게이팅 + 이메일 충돌 시 중복 생성 금지.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.config import settings
from app.models import School, User
from app.utils.security import hash_password
from tests.conftest import async_session_test


@pytest.fixture(autouse=True)
def _oauth_settings(seed_school: School, monkeypatch):
    """모든 OAuth 테스트에서 stub provider + 허용 도메인 + 기본 학교 강제."""
    monkeypatch.setattr(settings, "oauth_provider", "stub")
    monkeypatch.setattr(settings, "allowed_teacher_domains", ["allowed.edu", "test.com"])
    monkeypatch.setattr(settings, "oauth_default_school_id", str(seed_school.id))
    yield


@pytest.mark.asyncio
async def test_login_endpoint_returns_authorize_url(client: AsyncClient):
    res = await client.get("/api/v1/auth/oauth/google/login")
    assert res.status_code == 200
    assert "authorize_url" in res.json()


@pytest.mark.asyncio
async def test_allowed_domain_creates_teacher(client: AsyncClient):
    res = await client.get(
        "/api/v1/auth/oauth/google/callback",
        params={"code": "newteacher@allowed.edu"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["role"] == "teacher"
    assert "access_token" in body
    assert "refresh_token=" in res.headers.get("set-cookie", "")

    async with async_session_test() as session:
        count = await session.scalar(
            select(func.count()).select_from(User).where(User.email == "newteacher@allowed.edu")
        )
    assert count == 1


@pytest.mark.asyncio
async def test_disallowed_domain_rejected(client: AsyncClient):
    res = await client.get(
        "/api/v1/auth/oauth/google/callback",
        params={"code": "someone@gmail.com"},
    )
    assert res.status_code == 403
    assert res.json()["code"] == "AUTH_OAUTH_DOMAIN_NOT_ALLOWED"

    async with async_session_test() as session:
        count = await session.scalar(
            select(func.count()).select_from(User).where(User.email == "someone@gmail.com")
        )
    assert count == 0


@pytest.mark.asyncio
async def test_existing_email_logs_in_without_duplicate(client: AsyncClient, seed_school: School):
    # 기존 교사 (도메인 test.com은 허용 목록에 있음)
    async with async_session_test() as session:
        existing = User(
            school_id=seed_school.id,
            email="known@test.com",
            hashed_password=hash_password("password123"),
            role="teacher",
            name="기존교사",
        )
        session.add(existing)
        await session.commit()
        existing_id = str(existing.id)

    res = await client.get(
        "/api/v1/auth/oauth/google/callback",
        params={"code": "known@test.com"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["user_id"] == existing_id

    async with async_session_test() as session:
        count = await session.scalar(
            select(func.count()).select_from(User).where(User.email == "known@test.com")
        )
    assert count == 1  # 중복 생성 없음
