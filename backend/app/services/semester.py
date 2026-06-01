"""Shared semester helpers used by domains that need to bind events to a
specific (year, term) but lack an explicit FK on their own row.

The Semester model carries (year, term) only — no date range — so "current"
is derived from today's calendar date using the Korean academic calendar
(1학기 ≈ Mar–Aug, 2학기 ≈ Sep–Feb). Picking ``max(year, term)`` is wrong:
in June it returns 2학기 even though the live term is 1학기, hiding grades
entered for the current semester. Used by attendance, feedback, counseling
outbox stagers and the analytics read defaults (dashboard, distribution).
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.semester import Semester


def academic_year_term(today: date) -> tuple[int, int]:
    """Map a calendar date to its Korean academic (year, term).

    1학기는 3~8월, 2학기는 9월~다음 해 2월. 1~2월은 직전 학년도의 2학기다.
    """
    month = today.month
    if 3 <= month <= 8:
        return today.year, 1
    if month >= 9:
        return today.year, 2
    return today.year - 1, 2


async def current_semester_id(
    db: AsyncSession, *, today: date | None = None
) -> uuid.UUID | None:
    """Return the id of the calendar-current semester.

    오늘 날짜로 (학년도, 학기)를 계산해 해당 Semester를 찾는다. 그 행이 아직
    없으면(부트스트랩/데이터 공백) latest(year DESC, term DESC)로 폴백한다.
    학기 row가 하나도 없으면 None.
    """
    if today is None:
        today = date.today()
    year, term = academic_year_term(today)

    matched = await db.execute(
        select(Semester.id)
        .where(Semester.year == year, Semester.term == term)
        .limit(1)
    )
    sid = matched.scalar_one_or_none()
    if sid is not None:
        return sid

    latest = await db.execute(
        select(Semester.id)
        .order_by(Semester.year.desc(), Semester.term.desc())
        .limit(1)
    )
    return latest.scalar_one_or_none()
