import io

import pytest
from httpx import AsyncClient
from openpyxl import Workbook

from tests.conftest import async_session_test
from app.models.class_ import Class
from app.models.semester import Semester
from app.models.subject import Subject


def make_student_xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["이름", "번호", "생년월일", "성별", "연락처", "주소"])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_grade_xlsx(subjects: list[str], rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["번호", *subjects])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
async def seed_class(seed_teacher, seed_school) -> Class:
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
async def test_upload_students_xlsx_returns_result(auth_client_teacher: AsyncClient, seed_class: Class):
    content = make_student_xlsx([
        ["김철수", 1, "2010-03-15", "male", "010-1234-5678", "서울시"],
        ["이영희", 2, "2010-05-20", "female", None, None],
    ])
    resp = await auth_client_teacher.post(
        f"/api/v1/import/students/xlsx?class_id={seed_class.id}",
        files={
            "file": (
                "students.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 2
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_upload_grades_xlsx_returns_result(auth_client_teacher: AsyncClient, seed_class: Class):
    # Seed subjects and semester
    async with async_session_test() as session:
        ko = Subject(class_id=seed_class.id, name="국어")
        ma = Subject(class_id=seed_class.id, name="수학")
        session.add_all([ko, ma])
        sem = Semester(year=2026, term=1)
        session.add(sem)
        await session.commit()
        await session.refresh(sem)
        semester_id = sem.id

    # First import students
    students = make_student_xlsx([["김철수", 1, None, None, None, None], ["이영희", 2, None, None, None, None]])
    await auth_client_teacher.post(
        f"/api/v1/import/students/xlsx?class_id={seed_class.id}",
        files={
            "file": (
                "students.xlsx",
                students,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    # Now import grades
    content = make_grade_xlsx(["국어", "수학"], [[1, 90, 88], [2, 70, 77]])
    resp = await auth_client_teacher.post(
        f"/api/v1/import/grades/xlsx?class_id={seed_class.id}&semester_id={semester_id}",
        files={
            "file": (
                "grades.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # 2 students * 2 subjects = 4 grades
    assert data["created"] == 4
    assert isinstance(data["errors"], list)
