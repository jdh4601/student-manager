"""current_semester_id가 달력상 현재 학기를 고르는지 검증.

버그: '현재 학기'를 max(year, term)으로 정의해 6월(실제 1학기)에도 2학기를
반환했다 → 1학기에 입력한 성적이 대시보드 분포/챗봇에서 보이지 않았다.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.models.semester import Semester
from app.services.semester import current_semester_id
from tests.conftest import async_session_test


async def _semester_of(session, sid):
    return (
        await session.execute(select(Semester).where(Semester.id == sid))
    ).scalar_one()


async def test_current_semester_picks_calendar_term_not_highest_term():
    """6월에는 같은 해 term1·term2가 모두 있어도 1학기를 골라야 한다."""
    async with async_session_test() as session:
        session.add_all([Semester(year=2026, term=1), Semester(year=2026, term=2)])
        await session.commit()

        sid = await current_semester_id(session, today=date(2026, 6, 2))

        sem = await _semester_of(session, sid)
        assert (sem.year, sem.term) == (2026, 1)


async def test_current_semester_autumn_picks_term2():
    """9월에는 2학기를 골라야 한다."""
    async with async_session_test() as session:
        session.add_all([Semester(year=2026, term=1), Semester(year=2026, term=2)])
        await session.commit()

        sid = await current_semester_id(session, today=date(2026, 9, 15))

        sem = await _semester_of(session, sid)
        assert (sem.year, sem.term) == (2026, 2)


async def test_current_semester_falls_back_to_latest_without_calendar_match():
    """달력상 현재 학기 행이 없으면 latest(year,term DESC)로 폴백한다."""
    async with async_session_test() as session:
        session.add_all([Semester(year=2024, term=1), Semester(year=2025, term=2)])
        await session.commit()

        sid = await current_semester_id(session, today=date(2026, 6, 2))

        sem = await _semester_of(session, sid)
        assert (sem.year, sem.term) == (2025, 2)


async def test_current_semester_none_when_no_rows():
    async with async_session_test() as session:
        assert await current_semester_id(session, today=date(2026, 6, 2)) is None
