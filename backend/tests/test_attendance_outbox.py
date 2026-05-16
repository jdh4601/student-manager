"""SMS-78: Attendance UPSERT가 같은 트랜잭션에서 outbox INSERT를 발생시키는지 검증.

- 정상 commit: outbox row 1건 추가, payload·topic 정확
- update: 두 번째 outbox row(op=UPDATE) 추가
- duplicate (student_id, date) IntegrityError: attendance와 outbox 모두 rollback
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.errors import AppException
from app.models import Attendance, Class, School, Semester, Student, User
from app.models.outbox import Outbox
from app.services.student import create_attendance, update_attendance
from app.utils.security import hash_password
from tests.conftest import async_session_test


async def _seed_attendance_context(*, school: School):
    async with async_session_test() as session:
        teacher = User(
            school_id=school.id,
            email=f"t-{uuid.uuid4().hex[:6]}@test.com",
            hashed_password=hash_password("x"),
            role="teacher",
            name="김교사",
        )
        session.add(teacher)
        await session.commit()
        await session.refresh(teacher)

        cls = Class(
            school_id=school.id,
            teacher_id=teacher.id,
            grade=3,
            year=2026,
            name="3-1",
        )
        session.add(cls)
        await session.commit()
        await session.refresh(cls)

        student_user = User(
            school_id=school.id,
            email=f"s-{uuid.uuid4().hex[:6]}@test.com",
            hashed_password=hash_password("x"),
            role="student",
            name="학생A",
        )
        session.add(student_user)
        await session.commit()
        await session.refresh(student_user)

        student = Student(user_id=student_user.id, class_id=cls.id, student_number=1)
        session.add(student)
        await session.commit()
        await session.refresh(student)

        # current semester — the most recent (year DESC, term DESC) by convention
        semester = Semester(year=2026, term=1)
        session.add(semester)
        await session.commit()
        await session.refresh(semester)

        return teacher, student, semester


@pytest.mark.asyncio
async def test_create_attendance_emits_outbox_row(seed_school: School):
    teacher, student, semester = await _seed_attendance_context(school=seed_school)

    async with async_session_test() as session:
        att = await create_attendance(
            session,
            student_id=student.id,
            teacher_id=teacher.id,
            date_=date(2026, 5, 16),
            status="present",
            note=None,
        )
        rows = (await session.execute(select(Outbox))).scalars().all()

    assert len(rows) == 1
    row = rows[0]
    assert row.aggregate_type == "attendance"
    assert row.aggregate_id == att.id
    assert row.topic == "attendance_events"
    assert row.sent_at is None
    assert row.payload == {
        "attendance_id": str(att.id),
        "student_id": str(student.id),
        "semester_id": str(semester.id),
        "date": "2026-05-16",
        "status": "present",
        "op": "INSERT",
    }


@pytest.mark.asyncio
async def test_update_attendance_emits_second_outbox_row(seed_school: School):
    teacher, student, semester = await _seed_attendance_context(school=seed_school)

    async with async_session_test() as session:
        att = await create_attendance(
            session,
            student_id=student.id,
            teacher_id=teacher.id,
            date_=date(2026, 5, 16),
            status="absent",
            note=None,
        )

    async with async_session_test() as session:
        await update_attendance(
            session,
            attendance_id=att.id,
            teacher_id=teacher.id,
            status="late",
        )
        rows = (await session.execute(select(Outbox).order_by(Outbox.event_id))).scalars().all()

    assert [r.payload["op"] for r in rows] == ["INSERT", "UPDATE"]
    assert rows[-1].payload["status"] == "late"
    assert rows[-1].aggregate_id == att.id


@pytest.mark.asyncio
async def test_duplicate_attendance_rolls_back_both(seed_school: School):
    """중복 (student_id, date)는 IntegrityError → attendance와 outbox 모두 1건씩만 남음."""
    teacher, student, _semester = await _seed_attendance_context(school=seed_school)
    same_date = date(2026, 5, 16)

    async with async_session_test() as session:
        await create_attendance(
            session,
            student_id=student.id,
            teacher_id=teacher.id,
            date_=same_date,
            status="present",
            note=None,
        )

    with pytest.raises(AppException) as exc:
        async with async_session_test() as session:
            await create_attendance(
                session,
                student_id=student.id,
                teacher_id=teacher.id,
                date_=same_date,
                status="absent",
                note=None,
            )
    assert exc.value.code == "ATTENDANCE_DUPLICATE_DATE"

    async with async_session_test() as session:
        atts = (await session.execute(select(Attendance))).scalars().all()
        outbox = (await session.execute(select(Outbox))).scalars().all()

    assert len(atts) == 1
    assert len(outbox) == 1
    assert outbox[0].payload["status"] == "present"
