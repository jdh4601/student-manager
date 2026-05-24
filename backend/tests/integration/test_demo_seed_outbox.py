"""SMS-94: demo_seed가 outbox 행을 함께 stage하는지 검증.

demo_seed가 grade/feedback/counseling INSERT마다 outbox 행을 짝지어 만들면,
이미 SMS-54에서 검증된 publisher → kafka → analytics-worker 흐름에 의해
``analytics.agg_*``가 자동으로 채워진다. 본 테스트는 그 첫 단계
(demo_seed → outbox)만 검증하여 회귀를 방지한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

# scripts/demo_seed.py은 backend python path가 잡혀야 import 가능
from scripts import demo_seed  # noqa: E402

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_demo_seed_stages_outbox_rows_for_each_domain_insert(
    session_factory: async_sessionmaker[AsyncSession],
    clean_pipeline_tables: None,
) -> None:
    async with session_factory() as session:
        school = await demo_seed._get_or_create_school(session)
        teacher = await demo_seed._get_or_create_teacher(session, school)
        semesters = await demo_seed._ensure_semesters(session)
        cls = await demo_seed._ensure_class(session, school, teacher)
        subjects = await demo_seed._ensure_subjects(session, cls)
        students = await demo_seed._ensure_students(session, school, cls)
        await session.commit()

        n_grades = await demo_seed._seed_grades(
            session, students, subjects, semesters, teacher
        )
        n_feedbacks = await demo_seed._seed_feedbacks(session, students, teacher)
        n_counselings = await demo_seed._seed_counselings(session, students, teacher)
        await session.commit()

        # demo_seed should produce a non-trivial amount of domain rows
        assert n_grades > 0
        assert n_feedbacks > 0
        assert n_counselings > 0

        # outbox stages one row per domain INSERT
        grade_outbox = await session.execute(
            text(
                "SELECT count(*) FROM public.outbox WHERE topic = 'grade_events'"
            )
        )
        feedback_outbox = await session.execute(
            text(
                "SELECT count(*) FROM public.outbox WHERE topic = 'feedback_events'"
            )
        )
        counseling_outbox = await session.execute(
            text(
                "SELECT count(*) FROM public.outbox WHERE topic = 'counseling_events'"
            )
        )

    assert grade_outbox.scalar_one() == n_grades
    assert feedback_outbox.scalar_one() == n_feedbacks
    assert counseling_outbox.scalar_one() == n_counselings
