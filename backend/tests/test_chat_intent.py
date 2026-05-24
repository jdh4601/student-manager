"""SMS-97: 룰 기반 학기 의도 분류 단위 테스트.

resolve_semester_from_message는 (메시지, [Semester sorted desc]) → Semester | None.
DB 의존성을 빼고 학기 리스트를 직접 주입해 결정 규칙만 검증한다.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

from app.services.chat_intent import resolve_semester_from_message


@dataclass
class _Sem:
    id: uuid.UUID
    year: int
    term: int


def _semesters() -> list[_Sem]:
    """Sorted year DESC, term DESC — same shape current_semester_id returns."""
    return [
        _Sem(uuid.uuid4(), 2026, 1),
        _Sem(uuid.uuid4(), 2025, 2),
        _Sem(uuid.uuid4(), 2025, 1),
        _Sem(uuid.uuid4(), 2024, 2),
    ]


def test_no_semesters_returns_none() -> None:
    assert resolve_semester_from_message("이번 학기 영어 평균?", []) is None


def test_no_keyword_falls_back_to_latest() -> None:
    sems = _semesters()
    chosen = resolve_semester_from_message("우리 반 평균 알려줘", sems)
    assert chosen is sems[0]


def test_ibeon_keyword_picks_latest() -> None:
    sems = _semesters()
    assert resolve_semester_from_message("이번 학기 영어 평균이 어때?", sems) is sems[0]
    # 띄어쓰기 무관
    assert resolve_semester_from_message("이번학기 영어 평균", sems) is sems[0]


def test_jinan_keyword_picks_second_latest() -> None:
    sems = _semesters()
    assert resolve_semester_from_message("지난 학기 평균 비교", sems) is sems[1]
    assert resolve_semester_from_message("지난학기랑 차이", sems) is sems[1]


def test_jinan_with_only_one_semester_falls_back_to_latest() -> None:
    sems = [_Sem(uuid.uuid4(), 2026, 1)]
    # 지난 학기가 없으면 latest로 폴백 (잘못된 토큰 던지지 않음)
    assert resolve_semester_from_message("지난 학기 평균", sems) is sems[0]


def test_term_keyword_picks_latest_matching_term() -> None:
    sems = _semesters()
    # "1학기" 단독 — 가장 최근 year의 1학기 선택
    assert resolve_semester_from_message("1학기 영어 평균", sems) is sems[0]  # 2026,1
    # "2학기" 단독 — 가장 최근 year의 2학기 (2025,2)
    assert resolve_semester_from_message("2학기 평균은?", sems) is sems[1]


def test_ibeon_takes_precedence_over_term_number() -> None:
    """'이번' 키워드가 학기 번호 키워드보다 우선 — 가장 자연스러운 해석."""
    sems = _semesters()
    assert resolve_semester_from_message("이번 1학기", sems) is sems[0]


@pytest.mark.parametrize(
    "msg",
    [
        "1학기 평균",
        "2학기 평균",
        "이번 학기",
        "지난 학기",
        "그냥 평균 알려줘",
    ],
)
def test_always_returns_a_semester_when_list_non_empty(msg: str) -> None:
    sems = _semesters()
    assert resolve_semester_from_message(msg, sems) is not None
