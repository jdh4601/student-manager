"""SMS-54: end-to-end pipeline tests with real Kafka + Postgres.

Verifies the contract that ties together SMS-51 (outbox INSERT), SMS-52
(publisher worker), and SMS-53 (analytics consumer):

1. Pipeline SLA — an outbox row reaches ``analytics.agg_student_subject``
   within the 1-minute target (REQ-074 / Design Spec §9.6).
2. Publisher catch-up — rows committed before the publisher starts get
   drained; this is the post-broker-outage recovery path.
3. Consumer resume — restarting the consumer with the same ``group_id``
   resumes from the last committed offset, with no events lost or replayed
   into duplicate fact rows.

All tests are marked ``@pytest.mark.integration`` and skipped by default
to keep the unit test suite fast.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.outbox import Outbox
from app.workers import analytics, outbox_publisher

pytestmark = pytest.mark.integration


SLA_SECONDS = 60.0


async def _stage_outbox_row(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    grade_id: uuid.UUID,
    student_id: uuid.UUID,
    subject_id: uuid.UUID,
    semester_id: uuid.UUID,
    score: float,
    grade_rank: int,
    op: str = "INSERT",
) -> int:
    """INSERT one outbox row directly — bypasses operational seeding so the
    e2e tests can focus on the pipeline rather than student/class wiring."""
    async with session_factory() as db:
        row = Outbox(
            aggregate_type="grade",
            aggregate_id=grade_id,
            topic=analytics.GRADE_EVENTS_TOPIC,
            payload={
                "grade_id": str(grade_id),
                "student_id": str(student_id),
                "subject_id": str(subject_id),
                "semester_id": str(semester_id),
                "score": score,
                "grade_rank": grade_rank,
                "op": op,
            },
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row.event_id


async def _agg_subject_row(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    student_id: uuid.UUID,
    subject_id: uuid.UUID,
    semester_id: uuid.UUID,
) -> dict | None:
    async with session_factory() as db:
        result = await db.execute(
            text(
                """
                SELECT avg_score, max_score, min_score, sample_count, refreshed_at
                FROM analytics.agg_student_subject
                WHERE student_id = :s AND subject_id = :sub AND semester_id = :sem
                """
            ),
            {"s": student_id, "sub": subject_id, "sem": semester_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def _count_fact_events(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    student_id: uuid.UUID,
) -> int:
    async with session_factory() as db:
        result = await db.execute(
            text("SELECT count(*) FROM analytics.fact_grade_event WHERE student_id = :s"),
            {"s": student_id},
        )
        return int(result.scalar_one())


async def _wait_for(
    predicate, *, timeout: float, interval: float = 0.5, what: str = "condition"
):
    """Poll ``predicate()`` until it returns truthy or the timeout fires.

    Returns the truthy value so callers can use it as the test assertion target.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        value = await predicate()
        if value:
            return value
        if asyncio.get_event_loop().time() >= deadline:
            raise AssertionError(f"Timed out after {timeout}s waiting for {what}")
        await asyncio.sleep(interval)


def _build_publisher(kafka_bootstrap: str) -> AIOKafkaProducer:
    return AIOKafkaProducer(
        bootstrap_servers=kafka_bootstrap,
        enable_idempotence=True,
        acks="all",
    )


def _build_consumer(kafka_bootstrap: str, *, group_id: str) -> AIOKafkaConsumer:
    return AIOKafkaConsumer(
        analytics.GRADE_EVENTS_TOPIC,
        bootstrap_servers=kafka_bootstrap,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )


async def _spawn_publisher(
    *, kafka_bootstrap: str, session_factory, stop: asyncio.Event
) -> asyncio.Task:
    producer = _build_publisher(kafka_bootstrap)
    task = asyncio.create_task(
        outbox_publisher.run(
            producer=producer,
            session_factory=session_factory,
            poll_interval_idle=0.2,
            backoff_initial=0.2,
            backoff_max=1.0,
            stop_event=stop,
        )
    )
    return task


async def _spawn_consumer(
    *, kafka_bootstrap: str, session_factory, stop: asyncio.Event, group_id: str
) -> asyncio.Task:
    consumer = _build_consumer(kafka_bootstrap, group_id=group_id)
    task = asyncio.create_task(
        analytics.run(
            consumer=consumer,
            session_factory=session_factory,
            stop_event=stop,
            backoff_initial=0.2,
            backoff_max=1.0,
            getone_timeout=0.5,
        )
    )
    return task


async def _stop_task(task: asyncio.Task, stop: asyncio.Event) -> None:
    stop.set()
    try:
        await asyncio.wait_for(task, timeout=10.0)
    except asyncio.TimeoutError:
        task.cancel()
        with pytest.raises((asyncio.CancelledError, Exception)):
            await task


@pytest.mark.asyncio
async def test_pipeline_propagates_grade_event_within_sla(
    session_factory: async_sessionmaker[AsyncSession],
    kafka_bootstrap: str,
    clean_pipeline_tables: None,
    unique_uuids: dict[str, uuid.UUID],
):
    """An outbox row staged by an operational write must be reflected in
    analytics.agg_student_subject within ``SLA_SECONDS`` (REQ-074)."""
    student_id = unique_uuids["student"]
    subject_id = unique_uuids["subject"]
    semester_id = unique_uuids["semester"]
    grade_id = unique_uuids["grade"]

    pub_stop = asyncio.Event()
    cons_stop = asyncio.Event()
    publisher = await _spawn_publisher(
        kafka_bootstrap=kafka_bootstrap, session_factory=session_factory, stop=pub_stop
    )
    consumer = await _spawn_consumer(
        kafka_bootstrap=kafka_bootstrap,
        session_factory=session_factory,
        stop=cons_stop,
        group_id="sms54-sla",
    )

    try:
        started_at = datetime.utcnow()
        await _stage_outbox_row(
            session_factory,
            grade_id=grade_id,
            student_id=student_id,
            subject_id=subject_id,
            semester_id=semester_id,
            score=85.5,
            grade_rank=3,
            op="INSERT",
        )

        async def has_agg():
            return await _agg_subject_row(
                session_factory,
                student_id=student_id,
                subject_id=subject_id,
                semester_id=semester_id,
            )

        agg = await _wait_for(
            has_agg, timeout=SLA_SECONDS, interval=0.5, what="agg_student_subject row"
        )
        elapsed = (datetime.utcnow() - started_at).total_seconds()
    finally:
        await _stop_task(publisher, pub_stop)
        await _stop_task(consumer, cons_stop)

    assert agg is not None
    assert float(agg["avg_score"]) == pytest.approx(85.5)
    assert int(agg["sample_count"]) == 1
    assert elapsed <= SLA_SECONDS, f"pipeline SLA breached: {elapsed:.1f}s"


@pytest.mark.asyncio
async def test_publisher_drains_backlog_after_late_start(
    session_factory: async_sessionmaker[AsyncSession],
    kafka_bootstrap: str,
    clean_pipeline_tables: None,
    unique_uuids: dict[str, uuid.UUID],
):
    """Rows committed BEFORE the publisher boots must still be drained — this
    is the same code path that recovers from a broker outage (publisher
    polls ``WHERE sent_at IS NULL`` on every iteration)."""
    student_id = unique_uuids["student"]
    subject_id = unique_uuids["subject"]
    semester_id = unique_uuids["semester"]

    backlog = 5
    for i in range(backlog):
        await _stage_outbox_row(
            session_factory,
            grade_id=uuid.uuid4(),
            student_id=student_id,
            subject_id=subject_id,
            semester_id=semester_id,
            score=70.0 + i,
            grade_rank=4,
            op="INSERT",
        )

    pub_stop = asyncio.Event()
    cons_stop = asyncio.Event()
    publisher = await _spawn_publisher(
        kafka_bootstrap=kafka_bootstrap, session_factory=session_factory, stop=pub_stop
    )
    consumer = await _spawn_consumer(
        kafka_bootstrap=kafka_bootstrap,
        session_factory=session_factory,
        stop=cons_stop,
        group_id="sms54-catchup",
    )

    try:
        async def all_facts_landed():
            n = await _count_fact_events(session_factory, student_id=student_id)
            return n if n >= backlog else None

        count = await _wait_for(
            all_facts_landed,
            timeout=SLA_SECONDS,
            interval=0.5,
            what=f"{backlog} fact_grade_event rows",
        )
    finally:
        await _stop_task(publisher, pub_stop)
        await _stop_task(consumer, cons_stop)

    assert count == backlog, f"expected exactly {backlog} fact rows, got {count}"


@pytest.mark.asyncio
async def test_consumer_resumes_after_restart_without_loss(
    session_factory: async_sessionmaker[AsyncSession],
    kafka_bootstrap: str,
    clean_pipeline_tables: None,
    unique_uuids: dict[str, uuid.UUID],
):
    """Stop the consumer mid-flight, push more events while it's down,
    then bring it back with the same group_id — the new events must be
    processed and no event should be processed twice.

    Idempotency on duplicates is enforced by ``ON CONFLICT (event_id) DO
    NOTHING`` in the consumer, so this also verifies that contract holds
    against the real schema (not just the in-memory fake from SMS-53)."""
    student_id = unique_uuids["student"]
    subject_id = unique_uuids["subject"]
    semester_id = unique_uuids["semester"]

    first_batch = 3
    second_batch = 4
    group_id = f"sms54-resume-{uuid.uuid4().hex[:6]}"

    pub_stop = asyncio.Event()
    publisher = await _spawn_publisher(
        kafka_bootstrap=kafka_bootstrap, session_factory=session_factory, stop=pub_stop
    )

    cons_stop_1 = asyncio.Event()
    consumer_1 = await _spawn_consumer(
        kafka_bootstrap=kafka_bootstrap,
        session_factory=session_factory,
        stop=cons_stop_1,
        group_id=group_id,
    )

    try:
        for i in range(first_batch):
            await _stage_outbox_row(
                session_factory,
                grade_id=uuid.uuid4(),
                student_id=student_id,
                subject_id=subject_id,
                semester_id=semester_id,
                score=80.0 + i,
                grade_rank=3,
                op="INSERT",
            )

        async def first_batch_landed():
            n = await _count_fact_events(session_factory, student_id=student_id)
            return n if n >= first_batch else None

        await _wait_for(
            first_batch_landed, timeout=SLA_SECONDS, interval=0.5, what="first batch landed"
        )
    finally:
        await _stop_task(consumer_1, cons_stop_1)

    # Consumer is down — push more rows through. The publisher is still up.
    for i in range(second_batch):
        await _stage_outbox_row(
            session_factory,
            grade_id=uuid.uuid4(),
            student_id=student_id,
            subject_id=subject_id,
            semester_id=semester_id,
            score=90.0 + i,
            grade_rank=2,
            op="INSERT",
        )

    cons_stop_2 = asyncio.Event()
    consumer_2 = await _spawn_consumer(
        kafka_bootstrap=kafka_bootstrap,
        session_factory=session_factory,
        stop=cons_stop_2,
        group_id=group_id,
    )

    try:
        async def all_batches_landed():
            n = await _count_fact_events(session_factory, student_id=student_id)
            expected = first_batch + second_batch
            return n if n >= expected else None

        total = await _wait_for(
            all_batches_landed,
            timeout=SLA_SECONDS,
            interval=0.5,
            what="all events landed after resume",
        )
    finally:
        await _stop_task(consumer_2, cons_stop_2)
        await _stop_task(publisher, pub_stop)

    expected = first_batch + second_batch
    assert total == expected, (
        f"expected {expected} fact rows after resume, got {total} — "
        "either offset wasn't committed (replay → duplicates blocked, count still expected) "
        "or events were dropped"
    )
