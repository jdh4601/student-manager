"""SMS-93: PostgresStudentOverviewRepo batch methods — Postgres SQL behavior.

The chat context builder (SMS-95) will call these to avoid N+1 over the
담임 학급 학생 목록. Tests insert directly into ``analytics.agg_*`` and the
minimum ``public.*`` rows required for the subjects JOIN.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.analytics_query import PostgresStudentOverviewRepo

pytestmark = pytest.mark.integration


async def _seed_subjects(
    session: AsyncSession, *, names: list[str]
) -> dict[str, uuid.UUID]:
    """Insert one school + class + N subjects. Returns subject_name → id."""
    school_id = uuid.uuid4()
    class_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO public.schools (id, name) "
            "VALUES (:id, :name)"
        ),
        {"id": school_id, "name": "batch-test-school"},
    )
    await session.execute(
        text(
            "INSERT INTO public.classes (id, school_id, name, grade, year, teacher_id) "
            "VALUES (:id, :school_id, '1-1', 1, 2026, NULL)"
        ),
        {"id": class_id, "school_id": school_id},
    )
    subject_ids: dict[str, uuid.UUID] = {}
    for name in names:
        sid = uuid.uuid4()
        subject_ids[name] = sid
        await session.execute(
            text(
                "INSERT INTO public.subjects (id, class_id, name) "
                "VALUES (:id, :class_id, :name)"
            ),
            {"id": sid, "class_id": class_id, "name": name},
        )
    return subject_ids


async def _seed_agg_subject(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    subject_id: uuid.UUID,
    semester_id: uuid.UUID,
    avg_score: float,
    sample_count: int = 5,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO analytics.agg_student_subject
                (student_id, subject_id, semester_id, avg_score, max_score, min_score,
                 latest_rank, sample_count)
            VALUES (:sid, :subj, :sem, :avg, :avg, :avg, 1, :n)
            """
        ),
        {
            "sid": student_id,
            "subj": subject_id,
            "sem": semester_id,
            "avg": Decimal(str(avg_score)),
            "n": sample_count,
        },
    )


async def _seed_agg_overall(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    semester_id: uuid.UUID,
    avg_score: float,
    subject_count: int = 3,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO analytics.agg_student_overall
                (student_id, semester_id, total_score, avg_score, subject_count,
                 attendance_present_rate, feedback_count)
            VALUES (:sid, :sem, :total, :avg, :sc, 0.950, 1)
            """
        ),
        {
            "sid": student_id,
            "sem": semester_id,
            "total": Decimal(str(avg_score * subject_count)),
            "avg": Decimal(str(avg_score)),
            "sc": subject_count,
        },
    )


@pytest.mark.asyncio
async def test_get_overall_batch_empty_ids_returns_empty_dict(
    session_factory: async_sessionmaker[AsyncSession],
    clean_pipeline_tables: None,
) -> None:
    async with session_factory() as db:
        repo = PostgresStudentOverviewRepo(db)
        result = await repo.get_overall_batch(student_ids=[], semester_id=None)
    assert result == {}


@pytest.mark.asyncio
async def test_get_subjects_batch_empty_ids_returns_empty_dict(
    session_factory: async_sessionmaker[AsyncSession],
    clean_pipeline_tables: None,
) -> None:
    async with session_factory() as db:
        repo = PostgresStudentOverviewRepo(db)
        result = await repo.get_subjects_batch(student_ids=[], semester_id=None)
    assert result == {}


@pytest.mark.asyncio
async def test_get_overall_batch_groups_rows_by_student(
    session_factory: async_sessionmaker[AsyncSession],
    clean_pipeline_tables: None,
) -> None:
    s1, s2, s3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    sem = uuid.uuid4()

    async with session_factory() as db:
        await _seed_agg_overall(db, student_id=s1, semester_id=sem, avg_score=80.0)
        await _seed_agg_overall(db, student_id=s2, semester_id=sem, avg_score=90.0)
        # s3 has no overall row → must be absent from the result dict
        await db.commit()

        repo = PostgresStudentOverviewRepo(db)
        result = await repo.get_overall_batch(
            student_ids=[s1, s2, s3], semester_id=sem
        )

    assert set(result.keys()) == {s1, s2}
    assert result[s1].avg_score == 80.0
    assert result[s1].subject_count == 3
    assert result[s2].avg_score == 90.0


@pytest.mark.asyncio
async def test_get_subjects_batch_groups_rows_by_student(
    session_factory: async_sessionmaker[AsyncSession],
    clean_pipeline_tables: None,
) -> None:
    s1, s2 = uuid.uuid4(), uuid.uuid4()
    sem = uuid.uuid4()

    async with session_factory() as db:
        subjects = await _seed_subjects(db, names=["영어", "수학"])
        await _seed_agg_subject(
            db, student_id=s1, subject_id=subjects["영어"], semester_id=sem, avg_score=78
        )
        await _seed_agg_subject(
            db, student_id=s1, subject_id=subjects["수학"], semester_id=sem, avg_score=88
        )
        await _seed_agg_subject(
            db, student_id=s2, subject_id=subjects["영어"], semester_id=sem, avg_score=92
        )
        await db.commit()

        repo = PostgresStudentOverviewRepo(db)
        result = await repo.get_subjects_batch(
            student_ids=[s1, s2], semester_id=sem
        )

    assert set(result.keys()) == {s1, s2}
    s1_by_name = {row.name: row for row in result[s1]}
    assert s1_by_name["영어"].avg_score == 78.0
    assert s1_by_name["수학"].avg_score == 88.0
    assert len(result[s2]) == 1
    assert result[s2][0].name == "영어"
    assert result[s2][0].avg_score == 92.0


@pytest.mark.asyncio
async def test_get_subjects_batch_filters_by_semester(
    session_factory: async_sessionmaker[AsyncSession],
    clean_pipeline_tables: None,
) -> None:
    student = uuid.uuid4()
    sem_current = uuid.uuid4()
    sem_previous = uuid.uuid4()

    async with session_factory() as db:
        subjects = await _seed_subjects(db, names=["영어"])
        await _seed_agg_subject(
            db, student_id=student, subject_id=subjects["영어"],
            semester_id=sem_current, avg_score=78,
        )
        await _seed_agg_subject(
            db, student_id=student, subject_id=subjects["영어"],
            semester_id=sem_previous, avg_score=65,
        )
        await db.commit()

        repo = PostgresStudentOverviewRepo(db)
        current_only = await repo.get_subjects_batch(
            student_ids=[student], semester_id=sem_current
        )
        all_terms = await repo.get_subjects_batch(
            student_ids=[student], semester_id=None
        )

    assert [r.avg_score for r in current_only[student]] == [78.0]
    assert sorted(r.avg_score for r in all_terms[student]) == [65.0, 78.0]
