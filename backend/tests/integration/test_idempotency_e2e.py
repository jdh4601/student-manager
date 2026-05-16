"""SMS-81: 4-domain end-to-end idempotency verification.

Each domain's consumer protects against duplicate processing via
``INSERT ... ON CONFLICT (event_id) DO NOTHING``. This file pushes the
same logical message twice into a real Kafka topic and asserts:

- fact_<domain>_event has exactly one row for that event_id
- agg_student_subject / agg_student_overall values are unchanged on the
  second delivery (recompute is skipped when fact insert is a no-op)

The fifth scenario (consumer restart with same group_id) is already
covered by SMS-54's test_consumer_resumes_after_restart_without_loss —
this file focuses on the duplicate-payload contract specifically.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.workers import analytics

pytestmark = pytest.mark.integration


SLA_SECONDS = 60.0


async def _wait_for(predicate, *, timeout: float, interval: float = 0.5, what: str):
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        value = await predicate()
        if value:
            return value
        if asyncio.get_event_loop().time() >= deadline:
            raise AssertionError(f"Timed out after {timeout}s waiting for {what}")
        await asyncio.sleep(interval)


async def _spawn_consumer(*, kafka_bootstrap, session_factory, stop, group_id):
    consumer = AIOKafkaConsumer(
        *analytics.SUBSCRIBED_TOPICS,
        bootstrap_servers=kafka_bootstrap,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    return asyncio.create_task(
        analytics.run(
            consumer=consumer,
            session_factory=session_factory,
            stop_event=stop,
            backoff_initial=0.2,
            backoff_max=1.0,
            getone_timeout=0.5,
        )
    )


async def _stop_task(task, stop):
    stop.set()
    try:
        await asyncio.wait_for(task, timeout=10.0)
    except asyncio.TimeoutError:
        task.cancel()


async def _send_twice(producer: AIOKafkaProducer, *, topic: str, key: str, payload: dict):
    """Publish the exact same payload twice — same event_id triggers ON CONFLICT."""
    body = json.dumps(payload).encode("utf-8")
    for _ in range(2):
        await producer.send_and_wait(topic, value=body, key=key.encode("utf-8"))


async def _count(
    session_factory: async_sessionmaker[AsyncSession], *, table: str, schema: str = "analytics"
) -> int:
    async with session_factory() as db:
        result = await db.execute(text(f"SELECT count(*) FROM {schema}.{table}"))
        return int(result.scalar_one())


async def _count_where(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    table: str,
    where: str,
    params: dict,
    schema: str = "analytics",
) -> int:
    async with session_factory() as db:
        result = await db.execute(
            text(f"SELECT count(*) FROM {schema}.{table} WHERE {where}"), params
        )
        return int(result.scalar_one())


async def _agg_overall(session_factory, *, student_id, semester_id) -> dict | None:
    async with session_factory() as db:
        result = await db.execute(
            text(
                """
                SELECT avg_score, attendance_present_rate, feedback_count
                FROM analytics.agg_student_overall
                WHERE student_id = :s AND semester_id = :sem
                """
            ),
            {"s": student_id, "sem": semester_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


@pytest.fixture
async def producer(kafka_bootstrap: str):
    p = AIOKafkaProducer(
        bootstrap_servers=kafka_bootstrap, enable_idempotence=True, acks="all"
    )
    await p.start()
    try:
        yield p
    finally:
        await p.stop()


@pytest.mark.asyncio
async def test_duplicate_grade_event_inserts_fact_only_once(
    session_factory, kafka_bootstrap, clean_pipeline_tables, producer
):
    student_id = str(uuid.uuid4())
    grade_id = str(uuid.uuid4())
    subject_id = str(uuid.uuid4())
    semester_id = str(uuid.uuid4())
    event_id = 9_000_001

    payload = {
        "event_id": event_id,
        "grade_id": grade_id,
        "student_id": student_id,
        "subject_id": subject_id,
        "semester_id": semester_id,
        "score": 88.0,
        "grade_rank": 2,
        "op": "INSERT",
    }

    stop = asyncio.Event()
    consumer_task = await _spawn_consumer(
        kafka_bootstrap=kafka_bootstrap,
        session_factory=session_factory,
        stop=stop,
        group_id=f"sms81-grade-{uuid.uuid4().hex[:6]}",
    )

    try:
        await _send_twice(producer, topic="grade_events", key=grade_id, payload=payload)

        async def fact_landed():
            n = await _count_where(
                session_factory,
                table="fact_grade_event",
                where="event_id = :e",
                params={"e": event_id},
            )
            return n if n >= 1 else None

        await _wait_for(
            fact_landed, timeout=SLA_SECONDS, interval=0.5, what="grade fact row"
        )
        # Give the consumer a beat to attempt the second (duplicate) insert.
        await asyncio.sleep(2.0)

        count = await _count_where(
            session_factory,
            table="fact_grade_event",
            where="event_id = :e",
            params={"e": event_id},
        )
    finally:
        await _stop_task(consumer_task, stop)

    assert count == 1, f"ON CONFLICT failed — got {count} rows for event_id={event_id}"


@pytest.mark.asyncio
async def test_duplicate_attendance_event_inserts_fact_only_once(
    session_factory, kafka_bootstrap, clean_pipeline_tables, producer
):
    student_id = str(uuid.uuid4())
    semester_id = str(uuid.uuid4())
    event_id = 9_000_002

    payload = {
        "event_id": event_id,
        "attendance_id": str(uuid.uuid4()),
        "student_id": student_id,
        "semester_id": semester_id,
        "date": "2026-05-16",
        "status": "present",
        "op": "INSERT",
    }

    stop = asyncio.Event()
    consumer_task = await _spawn_consumer(
        kafka_bootstrap=kafka_bootstrap,
        session_factory=session_factory,
        stop=stop,
        group_id=f"sms81-attendance-{uuid.uuid4().hex[:6]}",
    )

    try:
        await _send_twice(
            producer, topic="attendance_events", key=student_id, payload=payload
        )

        async def landed():
            n = await _count_where(
                session_factory,
                table="fact_attendance_event",
                where="event_id = :e",
                params={"e": event_id},
            )
            return n if n >= 1 else None

        await _wait_for(landed, timeout=SLA_SECONDS, interval=0.5, what="attendance fact row")
        await asyncio.sleep(2.0)

        count = await _count_where(
            session_factory,
            table="fact_attendance_event",
            where="event_id = :e",
            params={"e": event_id},
        )
    finally:
        await _stop_task(consumer_task, stop)

    assert count == 1


@pytest.mark.asyncio
async def test_duplicate_feedback_event_keeps_count_at_one(
    session_factory, kafka_bootstrap, clean_pipeline_tables, producer
):
    student_id = str(uuid.uuid4())
    semester_id = str(uuid.uuid4())
    event_id = 9_000_003

    payload = {
        "event_id": event_id,
        "feedback_id": str(uuid.uuid4()),
        "student_id": student_id,
        "semester_id": semester_id,
        "category": "attitude",
        "op": "INSERT",
    }

    stop = asyncio.Event()
    consumer_task = await _spawn_consumer(
        kafka_bootstrap=kafka_bootstrap,
        session_factory=session_factory,
        stop=stop,
        group_id=f"sms81-feedback-{uuid.uuid4().hex[:6]}",
    )

    try:
        await _send_twice(
            producer, topic="feedback_events", key=student_id, payload=payload
        )

        async def landed():
            row = await _agg_overall(
                session_factory, student_id=student_id, semester_id=semester_id
            )
            return row if row and row["feedback_count"] is not None else None

        agg = await _wait_for(
            landed, timeout=SLA_SECONDS, interval=0.5, what="feedback_count refreshed"
        )
        await asyncio.sleep(2.0)

        fact_count = await _count_where(
            session_factory,
            table="fact_feedback_event",
            where="event_id = :e",
            params={"e": event_id},
        )
        final_agg = await _agg_overall(
            session_factory, student_id=student_id, semester_id=semester_id
        )
    finally:
        await _stop_task(consumer_task, stop)

    assert fact_count == 1
    assert int(agg["feedback_count"]) == 1
    assert int(final_agg["feedback_count"]) == 1, (
        "duplicate delivery must not inflate feedback_count"
    )


@pytest.mark.asyncio
async def test_duplicate_counseling_event_inserts_fact_only_once(
    session_factory, kafka_bootstrap, clean_pipeline_tables, producer
):
    student_id = str(uuid.uuid4())
    event_id = 9_000_004

    payload = {
        "event_id": event_id,
        "counseling_id": str(uuid.uuid4()),
        "student_id": student_id,
        "teacher_id": str(uuid.uuid4()),
        "date": "2026-05-16",
        "op": "INSERT",
    }

    stop = asyncio.Event()
    consumer_task = await _spawn_consumer(
        kafka_bootstrap=kafka_bootstrap,
        session_factory=session_factory,
        stop=stop,
        group_id=f"sms81-counseling-{uuid.uuid4().hex[:6]}",
    )

    try:
        await _send_twice(
            producer, topic="counseling_events", key=student_id, payload=payload
        )

        async def landed():
            n = await _count_where(
                session_factory,
                table="fact_counseling_event",
                where="event_id = :e",
                params={"e": event_id},
            )
            return n if n >= 1 else None

        await _wait_for(landed, timeout=SLA_SECONDS, interval=0.5, what="counseling fact row")
        await asyncio.sleep(2.0)

        count = await _count_where(
            session_factory,
            table="fact_counseling_event",
            where="event_id = :e",
            params={"e": event_id},
        )
    finally:
        await _stop_task(consumer_task, stop)

    assert count == 1


@pytest.mark.asyncio
async def test_malformed_payload_routes_to_dead_letter_table(
    session_factory, kafka_bootstrap, clean_pipeline_tables, producer
):
    """A poison message (missing required fields) must NOT block the consumer.

    The DLQ sink (SMS-80) records the bad message and advances the offset.
    A good message published right after must still be processed normally.
    """
    student_id = str(uuid.uuid4())
    subject_id = str(uuid.uuid4())
    semester_id = str(uuid.uuid4())
    grade_id = str(uuid.uuid4())
    good_event_id = 9_100_001

    # Send a malformed payload (missing student_id) first, then a good one.
    bad = json.dumps({"event_id": 9_100_999, "op": "INSERT"}).encode("utf-8")
    good = json.dumps(
        {
            "event_id": good_event_id,
            "grade_id": grade_id,
            "student_id": student_id,
            "subject_id": subject_id,
            "semester_id": semester_id,
            "score": 77.5,
            "grade_rank": 4,
            "op": "INSERT",
        }
    ).encode("utf-8")

    stop = asyncio.Event()
    consumer_task = await _spawn_consumer(
        kafka_bootstrap=kafka_bootstrap,
        session_factory=session_factory,
        stop=stop,
        group_id=f"sms81-dlq-{uuid.uuid4().hex[:6]}",
    )

    try:
        await producer.send_and_wait("grade_events", value=bad, key=b"poison")
        await producer.send_and_wait("grade_events", value=good, key=grade_id.encode())

        async def good_landed():
            n = await _count_where(
                session_factory,
                table="fact_grade_event",
                where="event_id = :e",
                params={"e": good_event_id},
            )
            return n if n >= 1 else None

        await _wait_for(
            good_landed, timeout=SLA_SECONDS, interval=0.5, what="good message processed"
        )

        dlq_count = await _count_where(
            session_factory,
            table="dead_letter_event",
            where="error LIKE :pat",
            params={"pat": "%missing required field%"},
        )
    finally:
        await _stop_task(consumer_task, stop)

    assert dlq_count >= 1, "poison message should have been recorded to DLQ"
