"""SMS-83: GET /api/v1/analytics/classes/{id}/distribution."""
from __future__ import annotations

import uuid as _uuid

import pytest
from httpx import AsyncClient

from app.dependencies.analytics import get_class_distribution_repo
from app.main import app
from app.models import Class, Semester, Subject
from app.services.analytics_query import bucketize, median
from app.services.semester import current_semester_id
from tests.conftest import async_session_test


class _FakeDistRepo:
    def __init__(self, scores: list[float] | None = None):
        self.scores = scores or []
        self.calls: list[tuple] = []

    async def get_student_avg_scores(self, *, class_id, subject_id, semester_id):
        self.calls.append((class_id, subject_id, semester_id))
        return self.scores


@pytest.fixture
def fake_dist_repo():
    repo = _FakeDistRepo()
    app.dependency_overrides[get_class_distribution_repo] = lambda: repo
    try:
        yield repo
    finally:
        app.dependency_overrides.pop(get_class_distribution_repo, None)


async def _bootstrap(teacher, school_id):
    async with async_session_test() as session:
        cls = Class(school_id=school_id, name="1-1", grade=1, year=2026, teacher_id=teacher.id)
        session.add(cls)
        await session.flush()
        sem = Semester(year=2026, term=1)
        subj = Subject(class_id=cls.id, name="Math")
        session.add_all([sem, subj])
        await session.commit()
        for x in (cls, sem, subj):
            await session.refresh(x)
        return cls, sem, subj


# ---------- pure-function tests (no FastAPI plumbing) ----------


def test_bucketize_empty():
    buckets = bucketize([])
    assert len(buckets) == 10
    assert all(b["count"] == 0 for b in buckets)
    assert buckets[0]["range"] == "0-9"
    assert buckets[-1]["range"] == "90-100"


def test_bucketize_bins_to_correct_ranges():
    # 95 → 90-100, 90 → 90-100, 89 → 80-89, 0 → 0-9, 9.999 → 0-9
    buckets = bucketize([0, 9.999, 89, 90, 95, 100])
    counts = {b["range"]: b["count"] for b in buckets}
    assert counts["0-9"] == 2
    assert counts["80-89"] == 1
    assert counts["90-100"] == 3


def test_median_odd_and_even():
    assert median([]) is None
    assert median([42.0]) == 42.0
    assert median([1, 2, 3, 4, 5]) == 3.0
    assert median([1, 2, 3, 4]) == 2.5


# ---------- API tests ----------


@pytest.mark.asyncio
async def test_distribution_returns_buckets_and_stats(
    auth_client_teacher: AsyncClient, seed_teacher, fake_dist_repo: _FakeDistRepo
):
    cls, sem, subj = await _bootstrap(seed_teacher, seed_teacher.school_id)
    fake_dist_repo.scores = [50, 60, 70, 80, 95]

    res = await auth_client_teacher.get(
        f"/api/v1/analytics/classes/{cls.id.hex}/distribution",
        params={"subject_id": subj.id.hex, "semester_id": sem.id.hex},
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["total_students"] == 5
    assert body["mean"] == pytest.approx(71.0)
    assert body["median"] == 70.0
    # bucket sanity: exactly 1 in 50-59, 60-69, 70-79, 80-89, 90-100
    counts = {b["range"]: b["count"] for b in body["buckets"]}
    assert counts["50-59"] == 1
    assert counts["60-69"] == 1
    assert counts["70-79"] == 1
    assert counts["80-89"] == 1
    assert counts["90-100"] == 1
    assert counts["0-9"] == 0


@pytest.mark.asyncio
async def test_distribution_defaults_to_current_semester(
    auth_client_teacher: AsyncClient, seed_teacher, fake_dist_repo: _FakeDistRepo
):
    """No semester_id → scope to the calendar-current semester, not all semesters.

    Omitting ``semester_id`` must delegate to ``current_semester_id`` (the
    calendar-current term, e.g. 1학기 in June) — never None (all semesters) and
    never the highest term number. Otherwise grades entered for the live term
    are hidden behind an empty future semester. Which term is "current" is
    covered deterministically in ``test_semester.py``.
    """
    cls, sem_2026_1, subj = await _bootstrap(seed_teacher, seed_teacher.school_id)
    async with async_session_test() as session:
        session.add_all([Semester(year=2025, term=1), Semester(year=2026, term=2)])
        await session.commit()
        expected = await current_semester_id(session)

    res = await auth_client_teacher.get(
        f"/api/v1/analytics/classes/{cls.id.hex}/distribution",
        params={"subject_id": subj.id.hex},  # semester_id intentionally omitted
    )
    assert res.status_code == 200, res.text
    # Scoped to the current semester — never None (which would mean all semesters).
    assert fake_dist_repo.calls[-1][2] is not None
    assert fake_dist_repo.calls[-1][2] == expected


@pytest.mark.asyncio
async def test_distribution_empty_data(
    auth_client_teacher: AsyncClient, seed_teacher, fake_dist_repo: _FakeDistRepo
):
    cls, sem, subj = await _bootstrap(seed_teacher, seed_teacher.school_id)
    res = await auth_client_teacher.get(
        f"/api/v1/analytics/classes/{cls.id.hex}/distribution",
        params={"subject_id": subj.id.hex, "semester_id": sem.id.hex},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total_students"] == 0
    assert body["mean"] is None
    assert body["median"] is None
    assert sum(b["count"] for b in body["buckets"]) == 0


@pytest.mark.asyncio
async def test_distribution_forbidden_for_other_teachers_class(
    auth_client_teacher: AsyncClient,
    auth_client_teacher_other: AsyncClient,
    seed_teacher,
    fake_dist_repo: _FakeDistRepo,
):
    cls, sem, subj = await _bootstrap(seed_teacher, seed_teacher.school_id)
    res = await auth_client_teacher_other.get(
        f"/api/v1/analytics/classes/{cls.id.hex}/distribution",
        params={"subject_id": subj.id.hex, "semester_id": sem.id.hex},
    )
    assert res.status_code == 403
    assert res.json() == {"detail": "권한이 부족합니다.", "code": "FORBIDDEN"}
    assert fake_dist_repo.calls == []


@pytest.mark.asyncio
async def test_distribution_missing_class_returns_404(
    auth_client_teacher: AsyncClient, fake_dist_repo: _FakeDistRepo
):
    res = await auth_client_teacher.get(
        f"/api/v1/analytics/classes/{_uuid.uuid4()}/distribution",
        params={"subject_id": str(_uuid.uuid4())},
    )
    assert res.status_code == 404
    assert res.json() == {"detail": "Class not found", "code": "CLASS_NOT_FOUND"}


@pytest.mark.asyncio
async def test_distribution_requires_subject_id(
    auth_client_teacher: AsyncClient, seed_teacher, fake_dist_repo: _FakeDistRepo
):
    cls, _sem, _subj = await _bootstrap(seed_teacher, seed_teacher.school_id)
    res = await auth_client_teacher.get(
        f"/api/v1/analytics/classes/{cls.id.hex}/distribution"
    )
    assert res.status_code == 422
