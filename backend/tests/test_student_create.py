import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import async_session_test
from app.models.class_ import Class


@pytest.fixture
async def seed_class(seed_teacher, seed_school) -> Class:
    """테스트용 반 생성"""
    async with async_session_test() as session:
        cls = Class(
            school_id=seed_school.id,
            name="1반",
            grade=1,
            year=2026,
            teacher_id=seed_teacher.id,
        )
        session.add(cls)
        await session.commit()
        await session.refresh(cls)
        return cls


@pytest.mark.asyncio
async def test_create_student_returns_201(auth_client_teacher: AsyncClient, seed_class: Class):
    resp = await auth_client_teacher.post(
        f"/api/v1/classes/{seed_class.id}/students",
        json={
            "name": "김철수",
            "student_number": 1,
            "gender": "male",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "김철수"
    assert data["student_number"] == 1
    assert data["gender"] == "male"


@pytest.mark.asyncio
async def test_create_student_duplicate_number_returns_409(auth_client_teacher: AsyncClient, seed_class: Class):
    body = {"name": "이영희", "student_number": 99}
    await auth_client_teacher.post(f"/api/v1/classes/{seed_class.id}/students", json=body)
    resp = await auth_client_teacher.post(f"/api/v1/classes/{seed_class.id}/students", json=body)
    assert resp.status_code == 409

