import io

import pytest

from tests.conftest import async_session_test
from app.models import Class, Semester, Subject


@pytest.mark.asyncio
async def test_import_students_csv(auth_client_teacher, seed_teacher):
    # class for teacher
    async with async_session_test() as session:
        cls = Class(school_id=seed_teacher.school_id, name="4-1", grade=4, year=2026, teacher_id=seed_teacher.id)
        session.add(cls)
        await session.commit()
        await session.refresh(cls)

    csv_content = f"email,name,class_id,student_number\nimp1@test.com,Imp One,{cls.id.hex},1\nimp1@test.com,Imp Dup,{cls.id.hex},2\n"
    files = {"file": ("students.csv", csv_content.encode("utf-8"), "text/csv")}
    res = await auth_client_teacher.post("/api/v1/import/students", files=files)
    assert res.status_code == 200
    body = res.json()
    assert body["created"] == 1
    assert body["skipped"] == 1


@pytest.mark.asyncio
async def test_import_grades_csv(auth_client_teacher, seed_teacher):
    # bootstrap class/semester/subject and student
    async with async_session_test() as session:
        cls = Class(school_id=seed_teacher.school_id, name="4-2", grade=4, year=2026, teacher_id=seed_teacher.id)
        session.add(cls)
        await session.flush()
        sem = Semester(year=2026, term=1)
        session.add(sem)
        await session.flush()
        subj = Subject(class_id=cls.id, name="History")
        session.add(subj)
        await session.commit()
        await session.refresh(cls)
        await session.refresh(sem)
        await session.refresh(subj)

    s_res = await auth_client_teacher.post(
        "/api/v1/users/students",
        json={"email": "gi@test.com", "name": "GI", "class_id": cls.id.hex, "student_number": 1},
    )
    student_id = s_res.json()["id"]

    csv_content = f"student_id,subject_id,semester_id,score\n{student_id},{subj.id.hex},{sem.id.hex},88\n"
    files = {"file": ("grades.csv", csv_content.encode("utf-8"), "text/csv")}
    res = await auth_client_teacher.post("/api/v1/import/grades", files=files)
    assert res.status_code == 200
    body = res.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 0

