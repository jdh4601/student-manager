"""LLM 컨텍스트 PII 마스킹.

학급 단위 통계 행을 LLM에 보내기 전에 학생 식별 정보를 토큰으로 치환한다.
표본 수가 5 미만이면 SmallSampleError를 발생시켜 단일 학생 식별을 차단한다.

Spec: docs/design-spec.md §10.3 — REQ-082, REQ-083, RISK-007.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

MIN_SAMPLE_SIZE = 5

_PII_FIELDS = ("student_id", "email", "phone")

# Fields to strip from nested ``subjects[]`` entries. ``subject_id`` is a UUID
# the LLM can't ground on — pure token cost.
_SUBJECT_NOISE_FIELDS = ("subject_id",)


def _index_to_token(i: int) -> str:
    """1-indexed 자리수 → ``학생A``..``학생Z``, ``학생AA``..``학생ZZ``.

    단일 알파벳 토큰만 쓰면 i ≥ 27에서 ``chr(91)='['`` 등 [A-Z] 밖의 문자가
    생성되어 라우터의 ``_TOKEN_PATTERN(r"학생[A-Z]{1,2}")``이 매칭하지 못한다.
    두 글자까지 확장하면 학생 26 + 26*26 = 702명까지 안전하다.
    """
    idx = i - 1
    if idx < 26:
        return f"학생{chr(65 + idx)}"
    idx -= 26
    first = idx // 26
    second = idx % 26
    return f"학생{chr(65 + first)}{chr(65 + second)}"


class SmallSampleError(Exception):
    """표본이 MIN_SAMPLE_SIZE 미만일 때 발생."""


def mask_context(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, UUID]]:
    """학생 식별 정보를 토큰으로 치환하고 매핑 테이블을 반환한다.

    Args:
        rows: 학급 단위 통계 행. `student_id`가 있으면 학생 단위 행으로 간주.

    Returns:
        (masked_rows, token_map) — masked_rows는 새 dict 리스트(입력 비파괴),
        token_map은 "학생A" 등 토큰에서 원본 student_id UUID로 매핑.

    Raises:
        SmallSampleError: rows 길이가 MIN_SAMPLE_SIZE 미만일 때.
    """
    if len(rows) < MIN_SAMPLE_SIZE:
        raise SmallSampleError(
            f"sample size {len(rows)} < {MIN_SAMPLE_SIZE} (k≥{MIN_SAMPLE_SIZE} required)"
        )

    token_map: dict[str, UUID] = {}
    masked_rows: list[dict[str, Any]] = []
    for i, row in enumerate(rows, start=1):
        if "student_id" not in row:
            masked_rows.append(row)
            continue

        token = _index_to_token(i)
        token_map[token] = row["student_id"]

        new_row = {
            **row,
            "student_name": token,
            "student_number": f"seq_{i:03d}",
        }
        for field in _PII_FIELDS:
            new_row.pop(field, None)
        if isinstance(new_row.get("subjects"), list):
            new_row["subjects"] = [
                {k: v for k, v in entry.items() if k not in _SUBJECT_NOISE_FIELDS}
                for entry in new_row["subjects"]
            ]
        masked_rows.append(new_row)

    return masked_rows, token_map
