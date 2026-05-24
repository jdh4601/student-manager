from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.llm_sanitizer import MIN_SAMPLE_SIZE, SmallSampleError, mask_context


def _student_rows(n: int) -> list[dict]:
    return [
        {
            "student_id": uuid4(),
            "student_name": f"학생원본{i}",
            "student_number": i,
            "score": 50 + i,
        }
        for i in range(1, n + 1)
    ]


def test_mask_context_replaces_names_and_numbers_for_k5():
    rows = _student_rows(5)
    original_ids = [r["student_id"] for r in rows]

    masked, token_map = mask_context(rows)

    assert [r["student_name"] for r in masked] == [
        "학생A",
        "학생B",
        "학생C",
        "학생D",
        "학생E",
    ]
    assert [r["student_number"] for r in masked] == [
        "seq_001",
        "seq_002",
        "seq_003",
        "seq_004",
        "seq_005",
    ]
    assert token_map == {
        "학생A": original_ids[0],
        "학생B": original_ids[1],
        "학생C": original_ids[2],
        "학생D": original_ids[3],
        "학생E": original_ids[4],
    }


def test_mask_context_preserves_non_pii_fields():
    rows = _student_rows(5)
    masked, _ = mask_context(rows)
    assert [r["score"] for r in masked] == [51, 52, 53, 54, 55]


def test_mask_context_strips_student_id_email_phone():
    rows = _student_rows(5)
    for r in rows:
        r["email"] = "x@example.com"
        r["phone"] = "010-0000-0000"

    masked, _ = mask_context(rows)

    for row in masked:
        assert "student_id" not in row
        assert "email" not in row
        assert "phone" not in row


def test_mask_context_raises_for_k4():
    with pytest.raises(SmallSampleError):
        mask_context(_student_rows(MIN_SAMPLE_SIZE - 1))


def test_mask_context_raises_for_empty():
    with pytest.raises(SmallSampleError):
        mask_context([])


def test_mask_context_passes_through_aggregate_rows_without_student_id():
    rows = [{"class_name": f"1-{i}", "avg_score": 70.0 + i} for i in range(1, 6)]
    masked, token_map = mask_context(rows)
    assert masked == rows
    assert token_map == {}


def test_mask_context_handles_full_class_through_z():
    rows = _student_rows(26)
    masked, token_map = mask_context(rows)
    assert masked[0]["student_name"] == "학생A"
    assert masked[25]["student_name"] == "학생Z"
    assert masked[25]["student_number"] == "seq_026"
    assert len(token_map) == 26


def test_mask_context_tokens_above_26_extend_to_two_letters():
    """B1 regression: 27명 이상이면 두 글자 토큰으로 확장된다.

    이전 구현(``f"학생{chr(64+i)}"``)은 i=27에서 ``학생[``를 만들어
    chat.py의 ``_TOKEN_PATTERN(r"학생[A-Z]")``이 silent drop 했다.
    평가용 시드(~30명) 경계에 정확히 걸리던 버그.
    """
    import re

    rows = _student_rows(28)
    masked, token_map = mask_context(rows)

    assert masked[25]["student_name"] == "학생Z"
    assert masked[26]["student_name"] == "학생AA"
    assert masked[27]["student_name"] == "학생AB"

    # chat.py 의 라우터 정규식 (두 글자 허용) 이 새 토큰을 모두 잡아낸다
    router_pattern = re.compile(r"학생[A-Z]{1,2}")
    for row in masked:
        token = row["student_name"]
        assert router_pattern.fullmatch(token), f"router regex misses {token!r}"
        assert token in token_map


def test_index_to_token_boundary_cases():
    """``_index_to_token`` 경계: 26 → 학생Z, 27 → 학생AA, 702 → 학생ZZ."""
    from app.services.llm_sanitizer import _index_to_token

    assert _index_to_token(1) == "학생A"
    assert _index_to_token(26) == "학생Z"
    assert _index_to_token(27) == "학생AA"
    assert _index_to_token(52) == "학생AZ"
    assert _index_to_token(53) == "학생BA"
    assert _index_to_token(702) == "학생ZZ"


def test_mask_context_drops_subject_id_from_nested_subjects():
    """SMS-96 — subjects[].subject_id is UUID noise the LLM can't use."""
    rows = _student_rows(5)
    sub_id = str(uuid4())
    for r in rows:
        r["subjects"] = [
            {
                "subject_id": sub_id,
                "name": "영어",
                "avg_score": 78.0,
                "max_score": 92.0,
            }
        ]

    masked, _ = mask_context(rows)

    for row in masked:
        assert row["subjects"], "subjects array must be preserved"
        for entry in row["subjects"]:
            assert "subject_id" not in entry
            # Useful fields stay
            assert entry["name"] == "영어"
            assert entry["avg_score"] == 78.0
            assert entry["max_score"] == 92.0


def test_mask_context_preserves_overall_object_as_is():
    """overall is a flat aggregate dict with no PII — pass-through."""
    rows = _student_rows(5)
    for r in rows:
        r["overall"] = {"avg_score": 82.4, "subject_count": 8}

    masked, _ = mask_context(rows)

    for row in masked:
        assert row["overall"] == {"avg_score": 82.4, "subject_count": 8}


def test_mask_context_does_not_mutate_input_rows():
    rows = _student_rows(5)
    original_first_name = rows[0]["student_name"]
    mask_context(rows)
    assert rows[0]["student_name"] == original_first_name
    assert "student_id" in rows[0]
