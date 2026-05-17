"""SMS-84: GET /api/v1/analytics/teachers/me/dashboard."""
from __future__ import annotations

import datetime as dt
import uuid as _uuid

import pytest
from httpx import AsyncClient

from app.dependencies.analytics import get_teacher_dashboard_repo
from app.main import app
from app.models import Class, Counseling, Feedback, Semester, Student
from app.services.analytics_query import ClassAggregate
from tests.conftest import async_session_test


class _FakeDashRepo:
    def __init__(self, aggs: list[ClassAggregate] | None = None):
        self.aggs = aggs or []
        self.received_semester_id = None
        self.received_class_ids = None

    async def get_class_aggregates(self, *, class_ids, semester_id):
        self.received_class_ids = list(class_ids)
        self.received_semester_id = semester_id
        return self.aggs


@pytest.fixture
def fake_dash_repo():
    repo = _FakeDashRepo()
    app.dependency_overrides[get_teacher_dashboard_repo] = lambda: repo
    try:
        yield repo
    finally:
        app.dependency_overrides.pop(get_teacher_dashboard_repo, None)


async def _seed_class(teacher, *, name: str):
    async with async_session_test() as session:
        cls = Class(
            school_id=teacher.school_id,
            name=name,
            grade=1,
            year=2026,
            teacher_id=teacher.id,
        )
        session.add(cls)
        await session.commit()
        await session.refresh(cls)
        return cls


async def _seed_semester(*, year: int, term: int):
    async with async_session_test() as session:
        sem = Semester(year=year, term=term)
        session.add(sem)
        await session.commit()
        await session.refresh(sem)
        return sem


async def _seed_student(cls, *, user_id, student_number: int = 1):
    async with async_session_test() as session:
        st = Student(class_id=cls.id, user_id=user_id, student_number=student_number)
        session.add(st)
        await session.commit()
        await session.refresh(st)
        return st


@pytest.mark.asyncio
async def test_dashboard_no_classes(
    auth_client_teacher: AsyncClient, seed_teacher, fake_dash_repo: _FakeDashRepo
):
    res = await auth_client_teacher.get("/api/v1/analytics/teachers/me/dashboard")
    assert res.status_code == 200
    body = res.json()
    assert body == {
        "classes": [],
        "recent_feedbacks_count": 0,
        "pending_counselings_count": 0,
    }
    # Repo still called (with empty class_ids)
    assert fake_dash_repo.received_class_ids == []


@pytest.mark.asyncio
async def test_dashboard_lists_owned_classes_with_aggregates(
    auth_client_teacher: AsyncClient, seed_teacher, fake_dash_repo: _FakeDashRepo
):
    cls_a = await _seed_class(seed_teacher, name="1-A")
    await _seed_class(seed_teacher, name="1-B")
    sem = await _seed_semester(year=2026, term=1)

    # Class A: 2 students, Class B: 0 students
    await _seed_student(cls_a, user_id=seed_teacher.id)  # bogus user_id ok for SQLite test
    fake_dash_repo.aggs = [
        ClassAggregate(class_id=cls_a.id, avg_score=82.5, attendance_rate=0.93),
    ]

    res = await auth_client_teacher.get(
        "/api/v1/analytics/teachers/me/dashboard",
        params={"semester_id": sem.id.hex},
    )
    assert res.status_code == 200
    body = res.json()
    classes_by_name = {c["name"]: c for c in body["classes"]}
    assert classes_by_name["1-A"]["student_count"] == 1
    assert classes_by_name["1-A"]["avg_score"] == pytest.approx(82.5)
    assert classes_by_name["1-A"]["attendance_rate"] == pytest.approx(0.93)
    # Class B: no aggregate → null
    assert classes_by_name["1-B"]["student_count"] == 0
    assert classes_by_name["1-B"]["avg_score"] is None
    assert classes_by_name["1-B"]["attendance_rate"] is None

    assert fake_dash_repo.received_semester_id == _uuid.UUID(sem.id.hex)


@pytest.mark.asyncio
async def test_dashboard_uses_current_semester_when_unset(
    auth_client_teacher: AsyncClient, seed_teacher, fake_dash_repo: _FakeDashRepo
):
    # Latest semester wins (year DESC, term DESC) — see services/semester.py
    older = await _seed_semester(year=2025, term=2)
    newer = await _seed_semester(year=2026, term=1)

    res = await auth_client_teacher.get("/api/v1/analytics/teachers/me/dashboard")
    assert res.status_code == 200
    assert fake_dash_repo.received_semester_id == newer.id
    assert fake_dash_repo.received_semester_id != older.id


@pytest.mark.asyncio
async def test_dashboard_excludes_other_teachers_classes(
    auth_client_teacher: AsyncClient,
    seed_teacher,
    seed_teacher_other,
    fake_dash_repo: _FakeDashRepo,
):
    await _seed_class(seed_teacher, name="MINE")
    await _seed_class(seed_teacher_other, name="OTHER")

    res = await auth_client_teacher.get("/api/v1/analytics/teachers/me/dashboard")
    assert res.status_code == 200
    body = res.json()
    names = {c["name"] for c in body["classes"]}
    assert names == {"MINE"}


@pytest.mark.asyncio
async def test_dashboard_recent_feedbacks_within_window(
    auth_client_teacher: AsyncClient, seed_teacher, fake_dash_repo: _FakeDashRepo
):
    cls = await _seed_class(seed_teacher, name="FB-CLS")
    student = await _seed_student(cls, user_id=seed_teacher.id)

    now = dt.datetime.utcnow()
    async with async_session_test() as session:
        # one within window (1 day ago), one outside (10 days ago)
        session.add(
            Feedback(
                student_id=student.id,
                teacher_id=seed_teacher.id,
                category="behavior",
                content="recent",
                created_at=now - dt.timedelta(days=1),
            )
        )
        session.add(
            Feedback(
                student_id=student.id,
                teacher_id=seed_teacher.id,
                category="behavior",
                content="old",
                created_at=now - dt.timedelta(days=10),
            )
        )
        await session.commit()

    res = await auth_client_teacher.get("/api/v1/analytics/teachers/me/dashboard")
    assert res.json()["recent_feedbacks_count"] == 1


@pytest.mark.asyncio
async def test_dashboard_pending_counselings_future_only(
    auth_client_teacher: AsyncClient, seed_teacher, fake_dash_repo: _FakeDashRepo
):
    cls = await _seed_class(seed_teacher, name="CS-CLS")
    student = await _seed_student(cls, user_id=seed_teacher.id)

    today = dt.date.today()
    async with async_session_test() as session:
        session.add(
            Counseling(
                student_id=student.id,
                teacher_id=seed_teacher.id,
                date=today + dt.timedelta(days=2),
                content="future",
            )
        )
        session.add(
            Counseling(
                student_id=student.id,
                teacher_id=seed_teacher.id,
                date=today - dt.timedelta(days=1),
                content="past",
            )
        )
        session.add(
            Counseling(
                student_id=student.id,
                teacher_id=seed_teacher.id,
                date=today,
                content="today",
            )
        )
        await session.commit()

    res = await auth_client_teacher.get("/api/v1/analytics/teachers/me/dashboard")
    # date > today → only the +2 day one
    assert res.json()["pending_counselings_count"] == 1


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client: AsyncClient):
    res = await client.get("/api/v1/analytics/teachers/me/dashboard")
    assert res.status_code in (401, 403)
