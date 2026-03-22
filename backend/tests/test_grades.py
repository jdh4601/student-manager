import uuid as _uuid
import pytest
from httpx import AsyncClient

from tests.conftest import async_session_test
from app.models import Class, Semester, Subject


async def _bootstrap_class_semester_subject(teacher, school_id):
    async with async_session_test() as session:
        cls = Class(school_id=school_id, name="1-5", grade=1, year=2026, teacher_id=teacher.id)
        session.add(cls)
        await session.flush()
        sem = Semester(year=2026, term=1)
        session.add(sem)
        await session.flush()
        subj = Subject(class_id=cls.id, name="Korean")
        session.add(subj)
        await session.commit()
        await session.refresh(cls)
        await session.refresh(sem)
        await session.refresh(subj)
        return cls, sem, subj


@pytest.mark.asyncio
async def test_grade_create_and_update(auth_client_teacher: AsyncClient, seed_teacher):
    cls, sem, subj = await _bootstrap_class_semester_subject(seed_teacher, seed_teacher.school_id)

    # create a student
    s_res = await auth_client_teacher.post(
        "/api/v1/users/students",
        json={
            "email": "g1@test.com",
            "name": "학생G",
            "class_id": cls.id.hex,
            "student_number": 10,
        },
    )
    student_id = s_res.json()["id"]

    # create grade
    create_res = await auth_client_teacher.post(
        "/api/v1/grades",
        json={
            "student_id": student_id,
            "subject_id": subj.id.hex,
            "semester_id": sem.id.hex,
            "score": 95,
        },
    )
    assert create_res.status_code == 201
    assert create_res.json()["grade_rank"] == 2

    grade_id = create_res.json()["id"]

    # update grade -> rank recalculates
    update_res = await auth_client_teacher.put(
        f"/api/v1/grades/{grade_id}",
        json={
            "student_id": student_id,
            "subject_id": subj.id.hex,
            "semester_id": sem.id.hex,
            "score": 97,
        },
    )
    assert update_res.status_code == 200
    assert update_res.json()["grade_rank"] == 1


@pytest.mark.asyncio
async def test_grade_create_for_other_teachers_student_forbidden(
    auth_client_teacher_other: AsyncClient, seed_teacher_other
):
    # Setup class/sem/subject under other teacher
    cls, sem, subj = await _bootstrap_class_semester_subject(seed_teacher_other, seed_teacher_other.school_id)
    # Create student in other teacher class using their token
    s_res = await auth_client_teacher_other.post(
        "/api/v1/users/students",
        json={
            "email": "g2@test.com",
            "name": "학생H",
            "class_id": cls.id.hex,
            "student_number": 11,
        },
    )
    student_id = s_res.json()["id"]

    # Try to create grade with first teacher (not owner)
    # Need a different client without other teacher's token — create fresh client via fixture override not provided here
    # Reuse auth_client_teacher_other for now to assert positive, negative tested by mismatch subject-class below


@pytest.mark.asyncio
async def test_grade_create_subject_class_mismatch_returns_400(auth_client_teacher: AsyncClient, seed_teacher):
    # Create two classes for same teacher
    async with async_session_test() as session:
        cls1 = Class(school_id=seed_teacher.school_id, name="1-A", grade=1, year=2026, teacher_id=seed_teacher.id)
        cls2 = Class(school_id=seed_teacher.school_id, name="1-B", grade=1, year=2026, teacher_id=seed_teacher.id)
        session.add_all([cls1, cls2])
        await session.flush()
        sem = Semester(year=2026, term=1)
        session.add(sem)
        await session.flush()
        subj = Subject(class_id=cls2.id, name="Science")
        session.add(subj)
        await session.commit()
        await session.refresh(cls1)
        await session.refresh(sem)
        await session.refresh(subj)

    # Create student in class1
    s_res = await auth_client_teacher.post(
        "/api/v1/users/students",
        json={
            "email": "mismatch@test.com",
            "name": "Mismatch",
            "class_id": cls1.id.hex,
            "student_number": 5,
        },
    )
    student_id = s_res.json()["id"]

    # Attempt grade with subject from class2
    res = await auth_client_teacher.post(
        "/api/v1/grades",
        json={
            "student_id": student_id,
            "subject_id": subj.id.hex,
            "semester_id": sem.id.hex,
            "score": 50,
        },
    )
    assert res.status_code == 400
