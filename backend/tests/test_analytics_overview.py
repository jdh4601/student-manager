"""SMS-82: GET /api/v1/analytics/students/{id}/overview + RBAC.

Analytics aggregates live in the Postgres-only ``analytics`` schema. To
keep this unit-level (SQLite), we override the StudentOverviewRepo
dependency with an in-memory fake — the same pattern the analytics worker
tests use (``tests/workers/test_analytics_consumer.py``). End-to-end SQL
behavior is covered separately by the Postgres integration suite.
"""
from __future__ import annotations

import uuid as _uuid

import pytest
from httpx import AsyncClient

from app.dependencies.analytics import get_student_overview_repo
from app.main import app
from app.models import Class, Semester, Subject
from app.services.analytics_query import OverallRow, SubjectRow
from tests.conftest import async_session_test


class _FakeRepo:
    """In-memory ``StudentOverviewRepo`` — records calls so RBAC tests can
    assert it was never reached when authorization fails."""

    def __init__(
        self,
        *,
        overall: OverallRow | None = None,
        subjects: list[SubjectRow] | None = None,
    ):
        self.overall = overall
        self.subjects = subjects or []
        self.calls: list[tuple[str, _uuid.UUID, _uuid.UUID | None]] = []

    async def get_overall(self, *, student_id, semester_id):
        self.calls.append(("overall", student_id, semester_id))
        return self.overall

    async def get_subjects(self, *, student_id, semester_id):
        self.calls.append(("subjects", student_id, semester_id))
        return self.subjects


@pytest.fixture
def fake_repo():
    repo = _FakeRepo()

    def _override():
        return repo

    app.dependency_overrides[get_student_overview_repo] = _override
    try:
        yield repo
    finally:
        app.dependency_overrides.pop(get_student_overview_repo, None)


async def _bootstrap_class_subjects(teacher, school_id, subject_names=("Korean",)):
    async with async_session_test() as session:
        cls = Class(school_id=school_id, name="1-5", grade=1, year=2026, teacher_id=teacher.id)
        session.add(cls)
        await session.flush()
        sem = Semester(year=2026, term=1)
        session.add(sem)
        await session.flush()
        subjects = [Subject(class_id=cls.id, name=name) for name in subject_names]
        for s in subjects:
            session.add(s)
        await session.commit()
        await session.refresh(cls)
        await session.refresh(sem)
        for s in subjects:
            await session.refresh(s)
        return cls, sem, subjects


async def _create_student(auth_client, cls, *, email: str, name: str, student_number: int) -> str:
    res = await auth_client.post(
        "/api/v1/users/students",
        json={"email": email, "name": name, "class_id": cls.id.hex, "student_number": student_number},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


@pytest.mark.asyncio
async def test_overview_returns_overall_and_subjects(
    auth_client_teacher: AsyncClient, seed_teacher, fake_repo: _FakeRepo
):
    cls, sem, (subj,) = await _bootstrap_class_subjects(seed_teacher, seed_teacher.school_id)
    student_id = await _create_student(
        auth_client_teacher, cls, email="ov1@test.com", name="개요학생", student_number=1
    )

    fake_repo.overall = OverallRow(
        avg_score=88.5,
        total_score=177.0,
        subject_count=2,
        attendance_present_rate=0.95,
        feedback_count=3,
    )
    fake_repo.subjects = [
        SubjectRow(
            subject_id=_uuid.UUID(subj.id.hex),
            name="Korean",
            avg_score=88.5,
            max_score=92.0,
            min_score=85.0,
            latest_rank=2,
            sample_count=2,
        )
    ]

    res = await auth_client_teacher.get(
        f"/api/v1/analytics/students/{student_id}/overview",
        params={"semester_id": sem.id.hex},
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["overall"] == {
        "avg_score": 88.5,
        "total_score": 177.0,
        "subject_count": 2,
        "attendance_present_rate": 0.95,
        "feedback_count": 3,
    }
    assert body["subjects"] == [
        {
            "subject_id": str(subj.id),
            "name": "Korean",
            "avg_score": 88.5,
            "max_score": 92.0,
            "min_score": 85.0,
            "latest_rank": 2,
            "sample_count": 2,
        }
    ]


@pytest.mark.asyncio
async def test_overview_empty_aggregates_returns_null_overall(
    auth_client_teacher: AsyncClient, seed_teacher, fake_repo: _FakeRepo
):
    cls, sem, _ = await _bootstrap_class_subjects(seed_teacher, seed_teacher.school_id)
    student_id = await _create_student(
        auth_client_teacher, cls, email="ov2@test.com", name="빈학생", student_number=2
    )

    # Repo returns nothing — student exists but no events projected yet
    res = await auth_client_teacher.get(
        f"/api/v1/analytics/students/{student_id}/overview",
        params={"semester_id": sem.id.hex},
    )

    assert res.status_code == 200
    body = res.json()
    assert body == {"overall": None, "subjects": []}


@pytest.mark.asyncio
async def test_overview_forbidden_for_other_teachers_student(
    auth_client_teacher: AsyncClient,
    auth_client_teacher_other: AsyncClient,
    seed_teacher,
    fake_repo: _FakeRepo,
):
    cls, sem, _ = await _bootstrap_class_subjects(seed_teacher, seed_teacher.school_id)
    student_id = await _create_student(
        auth_client_teacher, cls, email="ov3@test.com", name="권한학생", student_number=3
    )

    res = await auth_client_teacher_other.get(
        f"/api/v1/analytics/students/{student_id}/overview",
        params={"semester_id": sem.id.hex},
    )
    assert res.status_code == 403
    assert res.json() == {"detail": "권한이 부족합니다.", "code": "FORBIDDEN"}
    # Repo must not be called once authorization fails
    assert fake_repo.calls == []


@pytest.mark.asyncio
async def test_overview_missing_student_returns_404(
    auth_client_teacher: AsyncClient, fake_repo: _FakeRepo
):
    missing = str(_uuid.uuid4())
    res = await auth_client_teacher.get(f"/api/v1/analytics/students/{missing}/overview")
    assert res.status_code == 404
    assert res.json() == {"detail": "Student not found", "code": "STUDENT_NOT_FOUND"}


@pytest.mark.asyncio
async def test_overview_requires_auth(client: AsyncClient):
    res = await client.get(f"/api/v1/analytics/students/{_uuid.uuid4()}/overview")
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_overview_without_semester_calls_repo_with_none(
    auth_client_teacher: AsyncClient, seed_teacher, fake_repo: _FakeRepo
):
    cls, _sem, _ = await _bootstrap_class_subjects(seed_teacher, seed_teacher.school_id)
    student_id = await _create_student(
        auth_client_teacher, cls, email="ov4@test.com", name="전학기", student_number=4
    )

    res = await auth_client_teacher.get(
        f"/api/v1/analytics/students/{student_id}/overview"
    )
    assert res.status_code == 200
    # Both repo calls happen with semester_id=None (전 학기)
    assert all(call[2] is None for call in fake_repo.calls), fake_repo.calls
