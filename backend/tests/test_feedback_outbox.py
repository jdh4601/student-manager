"""SMS-79: Feedback CRUD가 같은 트랜잭션에서 outbox INSERT를 발생시키는지 검증.

- create: outbox row 1건, op=INSERT
- update: 두 번째 outbox row, op=UPDATE
- delete: 세 번째 outbox row, op=DELETE (delete 전에 stage)
- payload schema: feedback_id, student_id, semester_id, category, op
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models import Class, Feedback, School, Semester, Student, User
from app.models.outbox import Outbox
from app.services.feedback import create_feedback, delete_feedback, update_feedback
from app.utils.security import hash_password
from tests.conftest import async_session_test


async def _seed_feedback_context(*, school: School):
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

        semester = Semester(year=2026, term=1)
        session.add(semester)
        await session.commit()
        await session.refresh(semester)

        return teacher, student, semester


@pytest.mark.asyncio
async def test_create_feedback_emits_outbox_row(seed_school: School):
    teacher, student, semester = await _seed_feedback_context(school=seed_school)

    async with async_session_test() as session:
        fb = await create_feedback(
            session,
            student_id=student.id,
            teacher_id=teacher.id,
            category="attitude",
            content="수업 태도가 좋습니다.",
            is_visible_to_student=True,
            is_visible_to_parent=False,
        )
        rows = (await session.execute(select(Outbox))).scalars().all()

    assert len(rows) == 1
    row = rows[0]
    assert row.aggregate_type == "feedback"
    assert row.aggregate_id == fb.id
    assert row.topic == "feedback_events"
    assert row.payload == {
        "feedback_id": str(fb.id),
        "student_id": str(student.id),
        "semester_id": str(semester.id),
        "category": "attitude",
        "op": "INSERT",
    }


@pytest.mark.asyncio
async def test_update_feedback_emits_second_outbox_row(seed_school: School):
    teacher, student, _semester = await _seed_feedback_context(school=seed_school)

    async with async_session_test() as session:
        fb = await create_feedback(
            session,
            student_id=student.id,
            teacher_id=teacher.id,
            category="behavior",
            content="초안",
            is_visible_to_student=False,
            is_visible_to_parent=False,
        )

    async with async_session_test() as session:
        await update_feedback(
            session,
            feedback_id=fb.id,
            teacher_id=teacher.id,
            content="수정본",
        )
        rows = (await session.execute(select(Outbox).order_by(Outbox.event_id))).scalars().all()

    assert [r.payload["op"] for r in rows] == ["INSERT", "UPDATE"]


@pytest.mark.asyncio
async def test_delete_feedback_emits_delete_outbox_row(seed_school: School):
    teacher, student, _semester = await _seed_feedback_context(school=seed_school)

    async with async_session_test() as session:
        fb = await create_feedback(
            session,
            student_id=student.id,
            teacher_id=teacher.id,
            category="score",
            content="삭제할 항목",
            is_visible_to_student=False,
            is_visible_to_parent=False,
        )

    async with async_session_test() as session:
        await delete_feedback(session, feedback_id=fb.id, teacher_id=teacher.id)

    async with async_session_test() as session:
        rows = (await session.execute(select(Outbox).order_by(Outbox.event_id))).scalars().all()
        feedbacks = (await session.execute(select(Feedback))).scalars().all()

    assert [r.payload["op"] for r in rows] == ["INSERT", "DELETE"]
    assert rows[-1].payload["feedback_id"] == str(fb.id)
    assert feedbacks == []
