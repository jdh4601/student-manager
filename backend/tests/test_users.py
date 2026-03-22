import pytest
from httpx import AsyncClient

from tests.conftest import async_session_test
from app.models import Class, School, User
from app.utils.security import hash_password


@pytest.mark.asyncio
async def test_teacher_creates_student(auth_client_teacher: AsyncClient, seed_teacher: User, seed_school: School):
    # create a class for the teacher
    async with async_session_test() as session:
        cls = Class(school_id=seed_teacher.school_id, name="1-3", grade=1, year=2026, teacher_id=seed_teacher.id)
        session.add(cls)
        await session.commit()
        await session.refresh(cls)

    res = await auth_client_teacher.post(
        "/api/v1/users/students",
        json={
            "email": "s1@test.com",
            "name": "학생1",
            "class_id": cls.id.hex,
            "student_number": 1,
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "학생1"


@pytest.mark.asyncio
async def test_duplicate_email_returns_409(auth_client_teacher: AsyncClient, seed_teacher: User, seed_school: School):
    # create an existing user with same email
    async with async_session_test() as session:
        u = User(school_id=seed_school.id, email="dup@test.com", hashed_password=hash_password("pw"), role="student", name="dup")
        session.add(u)
        await session.commit()

    # create a class for the teacher
    async with async_session_test() as session:
        cls = Class(school_id=seed_teacher.school_id, name="1-4", grade=1, year=2026, teacher_id=seed_teacher.id)
        session.add(cls)
        await session.commit()
        await session.refresh(cls)

    res = await auth_client_teacher.post(
        "/api/v1/users/students",
        json={
            "email": "dup@test.com",
            "name": "학생X",
            "class_id": cls.id.hex,
            "student_number": 2,
        },
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_teacher_cannot_create_student_in_other_teachers_class(
    auth_client_teacher: AsyncClient, seed_teacher_other: User
):
    # Other teacher owns the class
    async with async_session_test() as session:
        cls = Class(
            school_id=seed_teacher_other.school_id,
            name="2-1",
            grade=2,
            year=2026,
            teacher_id=seed_teacher_other.id,
        )
        session.add(cls)
        await session.commit()
        await session.refresh(cls)

    res = await auth_client_teacher.post(
        "/api/v1/users/students",
        json={
            "email": "oob@test.com",
            "name": "越권",
            "class_id": cls.id.hex,
            "student_number": 3,
        },
    )
    assert res.status_code == 403
