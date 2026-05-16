"""SMS-53: analytics-worker — grade_events consumer.

The consumer logic is split into a pure `process_event` (testable with a fake
repository) and a thin aiokafka loop. These tests cover the business behavior:

- INSERT into fact_grade_event with the outbox `event_id` as the dedupe key
- UPSERT agg_student_subject + agg_student_overall (recompute via the repo)
- Idempotent: a duplicate event_id (already in fact) skips the agg recompute
- Malformed payloads (missing required fields) raise — message NOT committed
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

import pytest

from app.workers.analytics import AnalyticsRepository, decode_record, process_event


@dataclass
class FakeRepo(AnalyticsRepository):
    """In-memory repo that mirrors the Postgres contract."""

    fact_events: dict[int, dict] = field(default_factory=dict)
    agg_subject_calls: list[tuple[str, str, str]] = field(default_factory=list)
    agg_overall_calls: list[tuple[str, str]] = field(default_factory=list)

    async def insert_fact_event(self, *, event_id: int, payload: dict) -> bool:
        if event_id in self.fact_events:
            return False  # ON CONFLICT DO NOTHING
        self.fact_events[event_id] = payload
        return True

    async def recompute_agg_subject(
        self, *, student_id: str, subject_id: str, semester_id: str
    ) -> None:
        self.agg_subject_calls.append((student_id, subject_id, semester_id))

    async def recompute_agg_overall(self, *, student_id: str, semester_id: str) -> None:
        self.agg_overall_calls.append((student_id, semester_id))


def _payload(**overrides) -> dict:
    base = {
        "event_id": 101,
        "grade_id": str(uuid.uuid4()),
        "student_id": str(uuid.uuid4()),
        "subject_id": str(uuid.uuid4()),
        "semester_id": str(uuid.uuid4()),
        "score": 85.5,
        "grade_rank": 3,
        "op": "INSERT",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_process_event_inserts_fact_and_recomputes_aggs():
    repo = FakeRepo()
    p = _payload()

    await process_event(p, repo=repo)

    assert repo.fact_events[101]["grade_id"] == p["grade_id"]
    assert repo.fact_events[101]["score"] == 85.5
    assert repo.fact_events[101]["grade_rank"] == 3
    assert repo.fact_events[101]["op"] == "INSERT"
    assert repo.agg_subject_calls == [(p["student_id"], p["subject_id"], p["semester_id"])]
    assert repo.agg_overall_calls == [(p["student_id"], p["semester_id"])]


@pytest.mark.asyncio
async def test_process_event_handles_update_op():
    repo = FakeRepo()
    p = _payload(event_id=200, score=92.0, grade_rank=2, op="UPDATE")

    await process_event(p, repo=repo)

    assert repo.fact_events[200]["op"] == "UPDATE"
    assert len(repo.agg_subject_calls) == 1
    assert len(repo.agg_overall_calls) == 1


@pytest.mark.asyncio
async def test_process_event_idempotent_on_duplicate_event_id():
    """A retry with the same event_id must not insert twice nor re-aggregate."""
    repo = FakeRepo()
    p = _payload(event_id=300)

    await process_event(p, repo=repo)
    await process_event(p, repo=repo)  # retry

    assert len(repo.fact_events) == 1
    assert len(repo.agg_subject_calls) == 1, "agg recompute should be skipped on dupe"
    assert len(repo.agg_overall_calls) == 1


@pytest.mark.asyncio
async def test_process_event_accepts_null_score():
    """score=null is allowed (deleted/cleared grade) — fact row stored, aggs recomputed."""
    repo = FakeRepo()
    p = _payload(event_id=400, score=None, grade_rank=None)

    await process_event(p, repo=repo)

    assert repo.fact_events[400]["score"] is None
    assert repo.fact_events[400]["grade_rank"] is None
    assert len(repo.agg_subject_calls) == 1


@pytest.mark.asyncio
async def test_process_event_raises_on_missing_event_id():
    repo = FakeRepo()
    p = _payload()
    del p["event_id"]

    with pytest.raises(KeyError):
        await process_event(p, repo=repo)


@pytest.mark.asyncio
async def test_process_event_raises_on_missing_required_field():
    repo = FakeRepo()
    p = _payload()
    del p["student_id"]

    with pytest.raises(KeyError):
        await process_event(p, repo=repo)


def test_decode_record_parses_json_bytes():
    raw = json.dumps({"event_id": 1, "op": "INSERT"}).encode("utf-8")
    assert decode_record(raw) == {"event_id": 1, "op": "INSERT"}


def test_decode_record_rejects_non_object():
    with pytest.raises(ValueError):
        decode_record(b'"just a string"')
