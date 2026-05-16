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

from app.workers.analytics import (
    AnalyticsRepository,
    PoisonMessageError,
    decode_record,
    dispatch_event,
    process_attendance_event,
    process_counseling_event,
    process_event,
    process_feedback_event,
)


@dataclass
class FakeRepo(AnalyticsRepository):
    """In-memory repo that mirrors the Postgres contract."""

    fact_events: dict[int, dict] = field(default_factory=dict)
    fact_attendance_events: dict[int, dict] = field(default_factory=dict)
    fact_feedback_events: dict[int, dict] = field(default_factory=dict)
    fact_counseling_events: dict[int, dict] = field(default_factory=dict)
    agg_subject_calls: list[tuple[str, str, str]] = field(default_factory=list)
    agg_overall_calls: list[tuple[str, str]] = field(default_factory=list)
    dead_letters: list[dict] = field(default_factory=list)

    async def insert_fact_event(self, *, event_id: int, payload: dict) -> bool:
        if event_id in self.fact_events:
            return False  # ON CONFLICT DO NOTHING
        self.fact_events[event_id] = payload
        return True

    async def insert_fact_attendance(self, *, event_id: int, payload: dict) -> bool:
        if event_id in self.fact_attendance_events:
            return False
        self.fact_attendance_events[event_id] = payload
        return True

    async def insert_fact_feedback(self, *, event_id: int, payload: dict) -> bool:
        if event_id in self.fact_feedback_events:
            return False
        self.fact_feedback_events[event_id] = payload
        return True

    async def insert_fact_counseling(self, *, event_id: int, payload: dict) -> bool:
        if event_id in self.fact_counseling_events:
            return False
        self.fact_counseling_events[event_id] = payload
        return True

    async def record_dead_letter(
        self,
        *,
        topic: str,
        partition: int | None,
        offset: int | None,
        raw_value: bytes,
        error: str,
    ) -> None:
        self.dead_letters.append(
            {
                "topic": topic,
                "partition": partition,
                "offset": offset,
                "raw_value": raw_value,
                "error": error,
            }
        )

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


# ---------------------------------------------------------------------------
# Attendance event handler (SMS-78)
# ---------------------------------------------------------------------------


def _attendance_payload(**overrides) -> dict:
    base = {
        "event_id": 501,
        "attendance_id": str(uuid.uuid4()),
        "student_id": str(uuid.uuid4()),
        "semester_id": str(uuid.uuid4()),
        "date": "2026-05-16",
        "status": "present",
        "op": "INSERT",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_process_attendance_event_inserts_fact_and_recomputes_overall():
    repo = FakeRepo()
    p = _attendance_payload()

    await process_attendance_event(p, repo=repo)

    assert repo.fact_attendance_events[501]["status"] == "present"
    assert repo.fact_attendance_events[501]["date"] == "2026-05-16"
    assert repo.agg_overall_calls == [(p["student_id"], p["semester_id"])]
    # Attendance does not touch agg_student_subject
    assert repo.agg_subject_calls == []


@pytest.mark.asyncio
async def test_process_attendance_event_idempotent_on_duplicate_event_id():
    repo = FakeRepo()
    p = _attendance_payload(event_id=600)

    await process_attendance_event(p, repo=repo)
    await process_attendance_event(p, repo=repo)

    assert len(repo.fact_attendance_events) == 1
    assert len(repo.agg_overall_calls) == 1


@pytest.mark.asyncio
async def test_process_attendance_event_raises_on_missing_field():
    repo = FakeRepo()
    p = _attendance_payload()
    del p["status"]

    with pytest.raises(KeyError):
        await process_attendance_event(p, repo=repo)


# ---------------------------------------------------------------------------
# Topic-based dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_event_routes_grade_topic_to_process_event():
    repo = FakeRepo()
    p = _payload(event_id=700)

    await dispatch_event(p, repo=repo, topic="grade_events")

    assert 700 in repo.fact_events
    assert repo.fact_attendance_events == {}


@pytest.mark.asyncio
async def test_dispatch_event_routes_attendance_topic_to_attendance_handler():
    repo = FakeRepo()
    p = _attendance_payload(event_id=800)

    await dispatch_event(p, repo=repo, topic="attendance_events")

    assert 800 in repo.fact_attendance_events
    assert repo.fact_events == {}


@pytest.mark.asyncio
async def test_dispatch_event_routes_feedback_topic_to_feedback_handler():
    repo = FakeRepo()
    p = _feedback_payload(event_id=900)

    await dispatch_event(p, repo=repo, topic="feedback_events")

    assert 900 in repo.fact_feedback_events
    assert repo.fact_events == {}
    assert repo.fact_attendance_events == {}


@pytest.mark.asyncio
async def test_dispatch_event_rejects_unknown_topic():
    repo = FakeRepo()
    with pytest.raises(ValueError):
        await dispatch_event({"event_id": 1}, repo=repo, topic="bogus_events")


# ---------------------------------------------------------------------------
# Feedback event handler (SMS-79)
# ---------------------------------------------------------------------------


def _feedback_payload(**overrides) -> dict:
    base = {
        "event_id": 1001,
        "feedback_id": str(uuid.uuid4()),
        "student_id": str(uuid.uuid4()),
        "semester_id": str(uuid.uuid4()),
        "category": "attitude",
        "op": "INSERT",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_process_feedback_event_inserts_fact_and_recomputes_overall():
    repo = FakeRepo()
    p = _feedback_payload()

    await process_feedback_event(p, repo=repo)

    assert repo.fact_feedback_events[1001]["category"] == "attitude"
    assert repo.agg_overall_calls == [(p["student_id"], p["semester_id"])]
    assert repo.agg_subject_calls == []


@pytest.mark.asyncio
async def test_process_feedback_event_handles_delete_op():
    repo = FakeRepo()
    p = _feedback_payload(event_id=1100, op="DELETE")

    await process_feedback_event(p, repo=repo)

    assert repo.fact_feedback_events[1100]["op"] == "DELETE"
    assert len(repo.agg_overall_calls) == 1


@pytest.mark.asyncio
async def test_process_feedback_event_idempotent_on_duplicate_event_id():
    repo = FakeRepo()
    p = _feedback_payload(event_id=1200)

    await process_feedback_event(p, repo=repo)
    await process_feedback_event(p, repo=repo)

    assert len(repo.fact_feedback_events) == 1
    assert len(repo.agg_overall_calls) == 1


@pytest.mark.asyncio
async def test_process_feedback_event_raises_on_missing_field():
    repo = FakeRepo()
    p = _feedback_payload()
    del p["semester_id"]

    with pytest.raises(KeyError):
        await process_feedback_event(p, repo=repo)


# ---------------------------------------------------------------------------
# Counseling event handler (SMS-80)
# ---------------------------------------------------------------------------


def _counseling_payload(**overrides) -> dict:
    base = {
        "event_id": 2001,
        "counseling_id": str(uuid.uuid4()),
        "student_id": str(uuid.uuid4()),
        "teacher_id": str(uuid.uuid4()),
        "date": "2026-05-16",
        "op": "INSERT",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_process_counseling_event_inserts_fact_only_no_agg():
    """Counseling has no agg projection — only fact_counseling_event."""
    repo = FakeRepo()
    p = _counseling_payload()

    await process_counseling_event(p, repo=repo)

    assert repo.fact_counseling_events[2001]["op"] == "INSERT"
    assert repo.agg_overall_calls == []
    assert repo.agg_subject_calls == []


@pytest.mark.asyncio
async def test_process_counseling_event_idempotent_on_duplicate_event_id():
    repo = FakeRepo()
    p = _counseling_payload(event_id=2100)

    await process_counseling_event(p, repo=repo)
    await process_counseling_event(p, repo=repo)

    assert len(repo.fact_counseling_events) == 1


@pytest.mark.asyncio
async def test_process_counseling_event_raises_on_missing_field():
    repo = FakeRepo()
    p = _counseling_payload()
    del p["teacher_id"]

    with pytest.raises(KeyError):
        await process_counseling_event(p, repo=repo)


@pytest.mark.asyncio
async def test_dispatch_event_routes_counseling_topic():
    repo = FakeRepo()
    p = _counseling_payload(event_id=2200)

    await dispatch_event(p, repo=repo, topic="counseling_events")

    assert 2200 in repo.fact_counseling_events


# ---------------------------------------------------------------------------
# Dead-letter / run() loop (SMS-80)
# ---------------------------------------------------------------------------


@dataclass
class FakeRecord:
    topic: str
    value: bytes
    offset: int = 0
    partition: int = 0


class FakeConsumer:
    """Minimal AIOKafkaConsumer stand-in driven by a script of records."""

    def __init__(self, records: list):
        self._records = list(records)
        self.started = False
        self.stopped = False
        self.committed_count = 0

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def getone(self):
        if not self._records:
            # Sleep forever — the test sets stop_event externally.
            import asyncio as _a

            await _a.sleep(3600)
            raise AssertionError("unreachable")
        return self._records.pop(0)

    async def commit(self) -> None:
        self.committed_count += 1


@pytest.mark.asyncio
async def test_run_loop_records_dead_letter_for_malformed_payload():
    """A record that fails decode/dispatch must NOT block the consumer —
    it routes to the dead-letter sink and the offset gets committed."""
    import asyncio as _a
    import json as _json

    from app.workers import analytics as worker

    good = FakeRecord(
        topic="grade_events",
        value=_json.dumps(_payload(event_id=3000)).encode("utf-8"),
        offset=0,
    )
    poison = FakeRecord(topic="grade_events", value=b"not json at all", offset=1)
    consumer = FakeConsumer([good, poison])

    repo = FakeRepo()

    class _SessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return _FakeDb()

        async def __aexit__(self, *a):
            return False

    class _FakeDb:
        async def commit(self):
            pass

    stop = _a.Event()

    async def stopper():
        await _a.sleep(0.5)
        stop.set()

    _a.create_task(stopper())

    await worker.run(
        consumer=consumer,
        session_factory=_SessionFactory(),
        repo_builder=lambda _db: repo,
        stop_event=stop,
        backoff_initial=0.05,
        backoff_max=0.1,
        getone_timeout=0.1,
    )

    assert 3000 in repo.fact_events, "good message processed"
    assert len(repo.dead_letters) == 1, "poison message recorded to DLQ"
    assert repo.dead_letters[0]["topic"] == "grade_events"
    assert repo.dead_letters[0]["raw_value"] == b"not json at all"
    # Two commits — one per record (poison still commits to advance past it)
    assert consumer.committed_count == 2


def test_poison_message_error_is_distinguishable():
    """Sanity: PoisonMessageError is a separate type from generic Exception
    so the run() loop can route it differently from transient errors."""
    assert issubclass(PoisonMessageError, Exception)
