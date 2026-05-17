"""Read-only query layer for analytics.agg_* tables.

The router calls a ``StudentOverviewRepo`` through dependency injection.
Production uses ``PostgresStudentOverviewRepo`` (raw SQL against
``analytics.*``). Tests override the dependency with an in-memory fake to
keep the SQLite-based suite fast — the same pattern the analytics worker
uses for ``AnalyticsRepository`` (see ``app/workers/analytics.py``).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class OverallRow:
    avg_score: float | None
    total_score: float | None
    subject_count: int
    attendance_present_rate: float | None
    feedback_count: int


@dataclass(frozen=True)
class SubjectRow:
    subject_id: uuid.UUID
    name: str
    avg_score: float | None
    max_score: float | None
    min_score: float | None
    latest_rank: int | None
    sample_count: int


class StudentOverviewRepo(Protocol):
    async def get_overall(
        self, *, student_id: uuid.UUID, semester_id: uuid.UUID | None
    ) -> OverallRow | None: ...

    async def get_subjects(
        self, *, student_id: uuid.UUID, semester_id: uuid.UUID | None
    ) -> list[SubjectRow]: ...


class PostgresStudentOverviewRepo:
    """Raw-SQL impl against the Postgres ``analytics`` schema."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_overall(
        self, *, student_id: uuid.UUID, semester_id: uuid.UUID | None
    ) -> OverallRow | None:
        # When ``semester_id`` is None we sum across all semesters — the
        # number of rows per student is small (one per semester), so this is
        # a cheap aggregate, not a runtime roll-up over fact tables.
        if semester_id is None:
            stmt = text(
                """
                SELECT
                    avg(avg_score)                  AS avg_score,
                    sum(total_score)                AS total_score,
                    COALESCE(max(subject_count), 0) AS subject_count,
                    avg(attendance_present_rate)    AS attendance_present_rate,
                    COALESCE(sum(feedback_count), 0) AS feedback_count
                FROM analytics.agg_student_overall
                WHERE student_id = :student_id
                """
            )
            params = {"student_id": str(student_id)}
        else:
            stmt = text(
                """
                SELECT avg_score, total_score, subject_count,
                       attendance_present_rate, feedback_count
                FROM analytics.agg_student_overall
                WHERE student_id = :student_id AND semester_id = :semester_id
                """
            )
            params = {"student_id": str(student_id), "semester_id": str(semester_id)}

        result = await self._db.execute(stmt, params)
        row = result.mappings().first()
        if row is None or row["subject_count"] == 0 and row["avg_score"] is None:
            # No projections yet — caller decides whether to surface empty
            # ``overall`` or omit it entirely.
            return None
        return OverallRow(
            avg_score=_to_float(row["avg_score"]),
            total_score=_to_float(row["total_score"]),
            subject_count=int(row["subject_count"] or 0),
            attendance_present_rate=_to_float(row["attendance_present_rate"]),
            feedback_count=int(row["feedback_count"] or 0),
        )

    async def get_subjects(
        self, *, student_id: uuid.UUID, semester_id: uuid.UUID | None
    ) -> list[SubjectRow]:
        where = "WHERE a.student_id = :student_id"
        params: dict = {"student_id": str(student_id)}
        if semester_id is not None:
            where += " AND a.semester_id = :semester_id"
            params["semester_id"] = str(semester_id)
        stmt = text(
            f"""
            SELECT a.subject_id,
                   s.name        AS name,
                   a.avg_score,
                   a.max_score,
                   a.min_score,
                   a.latest_rank,
                   a.sample_count
            FROM analytics.agg_student_subject a
            JOIN public.subjects s ON s.id = a.subject_id
            {where}
            ORDER BY s.name
            """
        )
        result = await self._db.execute(stmt, params)
        return [
            SubjectRow(
                subject_id=uuid.UUID(str(r["subject_id"])),
                name=r["name"],
                avg_score=_to_float(r["avg_score"]),
                max_score=_to_float(r["max_score"]),
                min_score=_to_float(r["min_score"]),
                latest_rank=int(r["latest_rank"]) if r["latest_rank"] is not None else None,
                sample_count=int(r["sample_count"] or 0),
            )
            for r in result.mappings().all()
        ]


def _to_float(v) -> float | None:
    if v is None:
        return None
    return float(v)


class ClassDistributionRepo(Protocol):
    async def get_student_avg_scores(
        self,
        *,
        class_id: uuid.UUID,
        subject_id: uuid.UUID,
        semester_id: uuid.UUID | None,
    ) -> list[float]: ...


class PostgresClassDistributionRepo:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_student_avg_scores(
        self,
        *,
        class_id: uuid.UUID,
        subject_id: uuid.UUID,
        semester_id: uuid.UUID | None,
    ) -> list[float]:
        where = (
            "WHERE s.class_id = :class_id "
            "AND a.subject_id = :subject_id "
            "AND a.avg_score IS NOT NULL"
        )
        params: dict = {"class_id": str(class_id), "subject_id": str(subject_id)}
        if semester_id is not None:
            where += " AND a.semester_id = :semester_id"
            params["semester_id"] = str(semester_id)
        stmt = text(
            f"""
            SELECT a.avg_score
            FROM analytics.agg_student_subject a
            JOIN public.students s ON s.id = a.student_id
            {where}
            """
        )
        result = await self._db.execute(stmt, params)
        return [float(row[0]) for row in result.all()]


BUCKET_RANGES: tuple[tuple[int, int], ...] = tuple((lo, lo + 9) for lo in range(0, 100, 10))


def bucket_label(lo: int, hi: int) -> str:
    """Render a bucket range as ``"0-9"`` … ``"90-100"``.

    The top bucket includes 100 (10-point bins, scores are 0-100 inclusive).
    """
    return f"{lo}-{100 if lo == 90 else hi}"


def bucketize(scores: list[float]) -> list[dict]:
    """Bin scores into 10-point buckets. The 90-100 bucket includes 100."""
    counts = [0] * len(BUCKET_RANGES)
    for s in scores:
        idx = min(int(s // 10), len(BUCKET_RANGES) - 1)
        counts[idx] += 1
    return [
        {"range": bucket_label(lo, hi), "count": counts[i]}
        for i, (lo, hi) in enumerate(BUCKET_RANGES)
    ]


def median(scores: list[float]) -> float | None:
    if not scores:
        return None
    s = sorted(scores)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2


@dataclass(frozen=True)
class ClassAggregate:
    class_id: uuid.UUID
    avg_score: float | None
    attendance_rate: float | None


class TeacherDashboardRepo(Protocol):
    async def get_class_aggregates(
        self,
        *,
        class_ids: list[uuid.UUID],
        semester_id: uuid.UUID | None,
    ) -> list[ClassAggregate]: ...


class PostgresTeacherDashboardRepo:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_class_aggregates(
        self,
        *,
        class_ids: list[uuid.UUID],
        semester_id: uuid.UUID | None,
    ) -> list[ClassAggregate]:
        if not class_ids:
            return []
        where = "WHERE s.class_id = ANY(:class_ids)"
        params: dict = {"class_ids": [str(c) for c in class_ids]}
        if semester_id is not None:
            where += " AND a.semester_id = :semester_id"
            params["semester_id"] = str(semester_id)
        stmt = text(
            f"""
            SELECT s.class_id,
                   avg(a.avg_score)               AS avg_score,
                   avg(a.attendance_present_rate) AS attendance_rate
            FROM analytics.agg_student_overall a
            JOIN public.students s ON s.id = a.student_id
            {where}
            GROUP BY s.class_id
            """
        )
        result = await self._db.execute(stmt, params)
        return [
            ClassAggregate(
                class_id=uuid.UUID(str(row["class_id"])),
                avg_score=_to_float(row["avg_score"]),
                attendance_rate=_to_float(row["attendance_rate"]),
            )
            for row in result.mappings().all()
        ]
