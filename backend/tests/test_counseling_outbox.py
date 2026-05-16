"""SMS-80: Counseling CRUD가 같은 트랜잭션에서 outbox INSERT를 발생시키는지 검증."""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.models import Class, School, Student, User
from app.models.outbox import Outbox
from app.services.counseling import create_counseling, update_counseling
from app.utils.security import hash_password
from tests.conftest import async_session_test


async def _seed(*, school: School):
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

        return teacher, student


@pytest.mark.asyncio
async def test_create_counseling_emits_outbox_row(seed_school: School):
    teacher, student = await _seed(school=seed_school)

    async with async_session_test() as session:
        cs = await create_counseling(
            session,
            student_id=student.id,
            teacher_id=teacher.id,
            date=date(2026, 5, 16),
            content="초기 상담",
            next_plan="다음 주 추적",
            is_shared=True,
        )
        rows = (await session.execute(select(Outbox))).scalars().all()

    assert len(rows) == 1
    row = rows[0]
    assert row.aggregate_type == "counseling"
    assert row.aggregate_id == cs.id
    assert row.topic == "counseling_events"
    assert row.payload == {
        "counseling_id": str(cs.id),
        "student_id": str(student.id),
        "teacher_id": str(teacher.id),
        "date": "2026-05-16",
        "op": "INSERT",
    }


@pytest.mark.asyncio
async def test_update_counseling_emits_second_outbox_row(seed_school: School):
    teacher, student = await _seed(school=seed_school)

    async with async_session_test() as session:
        cs = await create_counseling(
            session,
            student_id=student.id,
            teacher_id=teacher.id,
            date=date(2026, 5, 16),
            content="초안",
            next_plan=None,
            is_shared=False,
        )

    async with async_session_test() as session:
        await update_counseling(
            session,
            counseling_id=cs.id,
            teacher_id=teacher.id,
            content="수정본",
        )
        rows = (await session.execute(select(Outbox).order_by(Outbox.event_id))).scalars().all()

    assert [r.payload["op"] for r in rows] == ["INSERT", "UPDATE"]
