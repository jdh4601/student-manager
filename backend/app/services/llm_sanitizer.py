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

        token = f"학생{chr(64 + i)}"
        token_map[token] = row["student_id"]

        new_row = {
            **row,
            "student_name": token,
            "student_number": f"seq_{i:03d}",
        }
        for field in _PII_FIELDS:
            new_row.pop(field, None)
        masked_rows.append(new_row)

    return masked_rows, token_map
