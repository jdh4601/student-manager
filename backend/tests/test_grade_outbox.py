"""SMS-51: Grade UPSERT가 같은 트랜잭션에서 outbox INSERT를 발생시키는지 검증.

- 정상 commit: outbox row 1건 추가, payload·topic 정확
- update: 두 번째 outbox row(op=UPDATE) 추가
- duplicate IntegrityError: grade와 outbox 모두 rollback (총 1건씩만 잔존)
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.errors import AppException
from app.models import Class, Grade, School, Semester, Student, Subject, User
from app.models.outbox import Outbox
from app.services.grade import create_grade, update_grade
from app.utils.security import hash_password
from tests.conftest import async_session_test


async def _seed_grade_context(*, school: School):
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

        subject = Subject(class_id=cls.id, name="수학")
        semester = Semester(year=2026, term=1)
        session.add_all([subject, semester])
        await session.commit()
        await session.refresh(subject)
        await session.refresh(semester)

        return teacher, student, subject, semester


@pytest.mark.asyncio
async def test_create_grade_emits_outbox_row(seed_school: School):
    teacher, student, subject, semester = await _seed_grade_context(school=seed_school)

    async with async_session_test() as session:
        grade = await create_grade(
            session,
            student_id=student.id,
            subject_id=subject.id,
            semester_id=semester.id,
            score=Decimal("85.5"),
            created_by=teacher.id,
            teacher_id=teacher.id,
        )
        rows = (await session.execute(select(Outbox))).scalars().all()

    assert len(rows) == 1
    row = rows[0]
    assert row.aggregate_type == "grade"
    assert row.aggregate_id == grade.id
    assert row.topic == "grade_events"
    assert row.sent_at is None
    assert row.payload == {
        "grade_id": str(grade.id),
        "student_id": str(student.id),
        "subject_id": str(subject.id),
        "semester_id": str(semester.id),
        "score": 85.5,
        "grade_rank": grade.grade_rank,
        "op": "INSERT",
    }


@pytest.mark.asyncio
async def test_update_grade_emits_second_outbox_row(seed_school: School):
    teacher, student, subject, semester = await _seed_grade_context(school=seed_school)

    async with async_session_test() as session:
        grade = await create_grade(
            session,
            student_id=student.id,
            subject_id=subject.id,
            semester_id=semester.id,
            score=Decimal("70"),
            created_by=teacher.id,
            teacher_id=teacher.id,
        )

    async with async_session_test() as session:
        await update_grade(
            session,
            grade_id=grade.id,
            score=Decimal("92"),
            teacher_id=teacher.id,
        )
        rows = (await session.execute(select(Outbox).order_by(Outbox.event_id))).scalars().all()

    assert [r.payload["op"] for r in rows] == ["INSERT", "UPDATE"]
    assert rows[-1].payload["score"] == 92.0
    assert rows[-1].aggregate_id == grade.id


@pytest.mark.asyncio
async def test_duplicate_grade_rolls_back_grade_and_outbox(seed_school: School):
    """중복 (student, subject, semester)는 IntegrityError → grade와 outbox 모두 1건씩만 남음."""
    teacher, student, subject, semester = await _seed_grade_context(school=seed_school)

    async with async_session_test() as session:
        await create_grade(
            session,
            student_id=student.id,
            subject_id=subject.id,
            semester_id=semester.id,
            score=Decimal("60"),
            created_by=teacher.id,
            teacher_id=teacher.id,
        )

    with pytest.raises(AppException) as exc:
        async with async_session_test() as session:
            await create_grade(
                session,
                student_id=student.id,
                subject_id=subject.id,
                semester_id=semester.id,
                score=Decimal("65"),
                created_by=teacher.id,
                teacher_id=teacher.id,
            )
    assert exc.value.code == "GRADE_DUPLICATE"

    async with async_session_test() as session:
        grades = (await session.execute(select(Grade))).scalars().all()
        outbox = (await session.execute(select(Outbox))).scalars().all()

    # Both must be exactly 1 — the duplicate INSERT's outbox row was rolled back
    # together with its grade row in the same TX.
    assert len(grades) == 1
    assert len(outbox) == 1
    assert outbox[0].payload["score"] == 60.0
