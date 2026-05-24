"""SMS-97: 룰 기반 학기 의도 분류.

사용자 메시지에서 학기 키워드를 추출해 ``Semester`` row를 고른다.
architecture.md §4.3의 "의도 분류 (rule)" 자리를 채운다.

규칙 (우선순위 순):
- "이번"  → 최신 학기
- "지난"  → 두 번째로 최신 (없으면 최신)
- "1학기" → year DESC 정렬에서 term=1인 첫 학기
- "2학기" → year DESC 정렬에서 term=2인 첫 학기
- 없음    → 최신 학기 (fallback, 학기가 하나라도 있으면 None 반환 안 함)

복잡한 패턴("작년 1학기", "2025년 2학기")은 v1에서 제외. 키워드 셋이
좁아 LLM tool calling 대비 비용 0/지연 0이라는 장점이 있다.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.semester import Semester


class _SemesterLike(Protocol):
    id: uuid.UUID
    year: int
    term: int


_IBEON = "이번"  # this term
_JINAN = "지난"  # previous term
_TERM_1 = "1학기"
_TERM_2 = "2학기"


def resolve_semester_from_message(
    message: str, semesters: list[_SemesterLike]
) -> _SemesterLike | None:
    """Pick a semester for the given user message.

    Args:
        message: 사용자의 원본 자연어 메시지.
        semesters: year DESC, term DESC로 정렬된 학기 리스트.

    Returns:
        선택된 학기 객체 또는 빈 리스트일 때만 None.
    """
    if not semesters:
        return None

    text = message.replace(" ", "")  # 띄어쓰기 무관 매칭

    if _IBEON in text:
        return semesters[0]
    if _JINAN in text:
        return semesters[1] if len(semesters) >= 2 else semesters[0]
    if _TERM_1 in text:
        for s in semesters:
            if s.term == 1:
                return s
        return semesters[0]
    if _TERM_2 in text:
        for s in semesters:
            if s.term == 2:
                return s
        return semesters[0]

    return semesters[0]


async def resolve_semester_id(message: str, db: AsyncSession) -> uuid.UUID | None:
    """DB-bound variant for router use. None이면 호출자는 None을 그대로
    fetch_student_rows에 전달 (전 학기 집계)."""
    result = await db.execute(
        select(Semester).order_by(Semester.year.desc(), Semester.term.desc())
    )
    semesters = list(result.scalars().all())
    chosen = resolve_semester_from_message(message, semesters)
    return chosen.id if chosen is not None else None
