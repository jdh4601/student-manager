"""SMS-95: PostgresChatContextRepo joins analytics aggregates into the
chat LLM context, with no N+1 over the 담임 학급 학생 목록.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.analytics_query import PostgresStudentOverviewRepo
from app.services.chat_context import PostgresChatContextRepo

pytestmark = pytest.mark.integration


async def _seed_school_class(
    session: AsyncSession, *, teacher_id: uuid.UUID | None
) -> tuple[uuid.UUID, uuid.UUID]:
    school_id = uuid.uuid4()
    class_id = uuid.uuid4()
    await session.execute(
        text("INSERT INTO public.schools (id, name) VALUES (:id, :name)"),
        {"id": school_id, "name": "chat-ctx-school"},
    )
    await session.execute(
        text(
            "INSERT INTO public.classes (id, school_id, name, grade, year, teacher_id) "
            "VALUES (:id, :school_id, '1-1', 1, 2026, :teacher_id)"
        ),
        {"id": class_id, "school_id": school_id, "teacher_id": teacher_id},
    )
    return school_id, class_id


async def _seed_teacher(session: AsyncSession, *, school_id: uuid.UUID) -> uuid.UUID:
    teacher_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO public.users
                (id, school_id, email, hashed_password, role, name)
            VALUES (:id, :school_id, :email, 'x', 'teacher', '담임')
            """
        ),
        {
            "id": teacher_id,
            "school_id": school_id,
            "email": f"t-{teacher_id}@test",
        },
    )
    return teacher_id


async def _seed_student(
    session: AsyncSession,
    *,
    school_id: uuid.UUID,
    class_id: uuid.UUID,
    name: str,
    seq: int,
) -> uuid.UUID:
    """Student는 user_id로 User에 연결되어 있고 name/school_id는 User 쪽에 있다."""
    user_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO public.users
                (id, school_id, email, hashed_password, role, name)
            VALUES (:id, :school_id, :email, 'x', 'student', :name)
            """
        ),
        {
            "id": user_id,
            "school_id": school_id,
            "email": f"s-{user_id}@test",
            "name": name,
        },
    )
    sid = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO public.students
                (id, user_id, class_id, student_number)
            VALUES (:id, :user_id, :class_id, :n)
            """
        ),
        {"id": sid, "user_id": user_id, "class_id": class_id, "n": seq},
    )
    return sid


async def _seed_subject(
    session: AsyncSession, *, class_id: uuid.UUID, name: str
) -> uuid.UUID:
    sub_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO public.subjects (id, class_id, name) "
            "VALUES (:id, :class_id, :name)"
        ),
        {"id": sub_id, "class_id": class_id, "name": name},
    )
    return sub_id


async def _seed_agg_subject(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    subject_id: uuid.UUID,
    semester_id: uuid.UUID,
    avg_score: float,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO analytics.agg_student_subject
                (student_id, subject_id, semester_id, avg_score, max_score, min_score,
                 latest_rank, sample_count)
            VALUES (:sid, :subj, :sem, :avg, :avg, :avg, 1, 5)
            """
        ),
        {
            "sid": student_id,
            "subj": subject_id,
            "sem": semester_id,
            "avg": Decimal(str(avg_score)),
        },
    )


async def _seed_agg_overall(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    semester_id: uuid.UUID,
    avg_score: float,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO analytics.agg_student_overall
                (student_id, semester_id, total_score, avg_score, subject_count,
                 attendance_present_rate, feedback_count)
            VALUES (:sid, :sem, :total, :avg, 3, 0.95, 1)
            """
        ),
        {
            "sid": student_id,
            "sem": semester_id,
            "total": Decimal(str(avg_score * 3)),
            "avg": Decimal(str(avg_score)),
        },
    )


@pytest.mark.asyncio
async def test_fetch_student_rows_includes_overall_and_subjects(
    session_factory: async_sessionmaker[AsyncSession],
    clean_pipeline_tables: None,
) -> None:
    sem = uuid.uuid4()

    async with session_factory() as db:
        school_id, class_id = await _seed_school_class(db, teacher_id=None)
        teacher_id = await _seed_teacher(db, school_id=school_id)
        await db.execute(
            text("UPDATE public.classes SET teacher_id = :tid WHERE id = :cid"),
            {"tid": teacher_id, "cid": class_id},
        )
        eng = await _seed_subject(db, class_id=class_id, name="영어")
        mat = await _seed_subject(db, class_id=class_id, name="수학")
        students = []
        for i in range(1, 6):  # 5명 (k≥5 통과)
            sid = await _seed_student(
                db, school_id=school_id, class_id=class_id,
                name=f"학생{i}", seq=i,
            )
            students.append(sid)
            await _seed_agg_subject(
                db, student_id=sid, subject_id=eng, semester_id=sem, avg_score=70 + i,
            )
            await _seed_agg_subject(
                db, student_id=sid, subject_id=mat, semester_id=sem, avg_score=80 + i,
            )
            await _seed_agg_overall(
                db, student_id=sid, semester_id=sem, avg_score=75 + i,
            )
        await db.commit()

        overview_repo = PostgresStudentOverviewRepo(db)
        chat_repo = PostgresChatContextRepo(db, overview_repo)
        rows = await chat_repo.fetch_student_rows(
            teacher_id=teacher_id,
            school_id=school_id,
            semester_id=sem,
        )

    assert len(rows) == 5
    by_name = {r["student_name"]: r for r in rows}
    row1 = by_name["학생1"]
    assert row1["class_name"] == "1-1"
    assert row1["overall"]["avg_score"] == 76.0
    assert row1["overall"]["subject_count"] == 3
    subjects_by_name = {s["name"]: s for s in row1["subjects"]}
    assert subjects_by_name["영어"]["avg_score"] == 71.0
    assert subjects_by_name["수학"]["avg_score"] == 81.0


@pytest.mark.asyncio
async def test_fetch_student_rows_handles_missing_aggregates(
    session_factory: async_sessionmaker[AsyncSession],
    clean_pipeline_tables: None,
) -> None:
    """Students with no analytics projection yet get null overall + empty subjects."""
    async with session_factory() as db:
        school_id, class_id = await _seed_school_class(db, teacher_id=None)
        teacher_id = await _seed_teacher(db, school_id=school_id)
        await db.execute(
            text("UPDATE public.classes SET teacher_id = :tid WHERE id = :cid"),
            {"tid": teacher_id, "cid": class_id},
        )
        for i in range(1, 6):
            await _seed_student(
                db, school_id=school_id, class_id=class_id,
                name=f"학생{i}", seq=i,
            )
        await db.commit()

        overview_repo = PostgresStudentOverviewRepo(db)
        chat_repo = PostgresChatContextRepo(db, overview_repo)
        rows = await chat_repo.fetch_student_rows(
            teacher_id=teacher_id, school_id=school_id, semester_id=None,
        )

    assert len(rows) == 5
    for row in rows:
        assert row["overall"] is None
        assert row["subjects"] == []
