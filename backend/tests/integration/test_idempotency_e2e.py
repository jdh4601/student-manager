"""End-to-end idempotency + dead-letter verification (post ADR-003).

The LISTEN/NOTIFY + SKIP LOCKED pipeline gives idempotency via two layers:

1. ``processed_at IS NOT NULL`` filter — the worker simply won't reclaim a
   row that's already been processed. This is the common-case dedupe.
2. ``INSERT ... ON CONFLICT (event_id) DO NOTHING`` on every ``analytics.fact_*``
   table — defence in depth. Tested here by forcing a re-process: clear
   ``processed_at`` after the first run so the boot catch-up re-claims the
   row, then assert the fact row count stays at 1.

The dead-letter test stages a malformed outbox row and verifies the worker
records it to ``analytics.dead_letter_event`` and marks ``processed_at`` so
the row stops blocking the queue.
"""
from __future__ import annotations

import asyncio
import uuid

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.outbox import Outbox
from app.workers import analytics, outbox_publisher

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


async def _spawn_publisher(*, session_factory, stop):
    return asyncio.create_task(
        outbox_publisher.run(
            session_factory=session_factory,
            poll_interval_idle=0.2,
            backoff_initial=0.2,
            backoff_max=1.0,
            stop_event=stop,
        )
    )


async def _spawn_worker(*, pg_raw_dsn: str, session_factory, stop):
    listener = await asyncpg.connect(pg_raw_dsn)
    task = asyncio.create_task(
        analytics.run(
            listener=listener,
            session_factory=session_factory,
            stop_event=stop,
            catchup_interval=1.0,
            max_retries=3,
        )
    )
    return task, listener


async def _stop_task(task, stop):
    stop.set()
    try:
        await asyncio.wait_for(task, timeout=10.0)
    except asyncio.TimeoutError:
        task.cancel()


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


async def _stage_outbox(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    aggregate_type: str,
    topic: str,
    payload: dict,
) -> int:
    async with session_factory() as db:
        row = Outbox(
            aggregate_type=aggregate_type,
            aggregate_id=uuid.uuid4(),
            topic=topic,
            payload=payload,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row.event_id


@pytest.mark.asyncio
async def test_replay_after_processed_at_reset_does_not_double_count(
    session_factory: async_sessionmaker[AsyncSession],
    pg_raw_dsn: str,
    clean_pipeline_tables: None,
):
    """ON CONFLICT(event_id) keeps fact_grade_event at one row even when the
    worker is forced to re-process the same outbox row.

    Real-world trigger: a worker crashes after ``INSERT ON CONFLICT`` and
    before the ``processed_at`` mark commits — the next catch-up re-claims
    the row. The fact PK is the safety net.
    """
    student_id = str(uuid.uuid4())
    subject_id = str(uuid.uuid4())
    semester_id = str(uuid.uuid4())
    grade_id = str(uuid.uuid4())

    pub_stop = asyncio.Event()
    cons_stop = asyncio.Event()
    publisher = await _spawn_publisher(session_factory=session_factory, stop=pub_stop)
    worker, listener = await _spawn_worker(
        pg_raw_dsn=pg_raw_dsn, session_factory=session_factory, stop=cons_stop
    )

    try:
        event_id = await _stage_outbox(
            session_factory,
            aggregate_type="grade",
            topic=analytics.GRADE_EVENTS_TOPIC,
            payload={
                "grade_id": grade_id,
                "student_id": student_id,
                "subject_id": subject_id,
                "semester_id": semester_id,
                "score": 88.0,
                "grade_rank": 2,
                "op": "INSERT",
            },
        )

        async def fact_landed():
            n = await _count_where(
                session_factory,
                table="fact_grade_event",
                where="event_id = :e",
                params={"e": event_id},
            )
            return n if n >= 1 else None

        await _wait_for(fact_landed, timeout=SLA_SECONDS, interval=0.5, what="initial fact")

        # Force a replay: clear processed_at so the next catch-up tick reclaims.
        async with session_factory() as db:
            await db.execute(
                text("UPDATE public.outbox SET processed_at = NULL WHERE event_id = :e"),
                {"e": event_id},
            )
            await db.commit()

        # Wait for catch-up to fire (interval=1.0) + processing.
        await asyncio.sleep(3.0)

        # And confirm the worker did re-mark processed_at — meaning it
        # genuinely re-ran the dispatcher and hit the ON CONFLICT path.
        async with session_factory() as db:
            result = await db.execute(
                text("SELECT processed_at FROM public.outbox WHERE event_id = :e"),
                {"e": event_id},
            )
            processed_at = result.scalar_one()
        assert processed_at is not None, "worker did not re-claim the outbox row"

        count = await _count_where(
            session_factory,
            table="fact_grade_event",
            where="event_id = :e",
            params={"e": event_id},
        )
    finally:
        await _stop_task(worker, cons_stop)
        await _stop_task(publisher, pub_stop)

    assert count == 1, f"ON CONFLICT broken — got {count} rows for event_id={event_id}"


@pytest.mark.asyncio
async def test_malformed_outbox_payload_routes_to_dead_letter(
    session_factory: async_sessionmaker[AsyncSession],
    pg_raw_dsn: str,
    clean_pipeline_tables: None,
):
    """A poison outbox row (missing required field) must not block the queue.

    The worker dead-letters it, marks ``processed_at``, and the next good
    row published right after must still process normally.
    """
    student_id = str(uuid.uuid4())
    subject_id = str(uuid.uuid4())
    semester_id = str(uuid.uuid4())
    grade_id = str(uuid.uuid4())

    pub_stop = asyncio.Event()
    cons_stop = asyncio.Event()
    publisher = await _spawn_publisher(session_factory=session_factory, stop=pub_stop)
    worker, listener = await _spawn_worker(
        pg_raw_dsn=pg_raw_dsn, session_factory=session_factory, stop=cons_stop
    )

    try:
        bad_event_id = await _stage_outbox(
            session_factory,
            aggregate_type="grade",
            topic=analytics.GRADE_EVENTS_TOPIC,
            payload={"op": "INSERT"},  # missing every required field but op
        )
        good_event_id = await _stage_outbox(
            session_factory,
            aggregate_type="grade",
            topic=analytics.GRADE_EVENTS_TOPIC,
            payload={
                "grade_id": grade_id,
                "student_id": student_id,
                "subject_id": subject_id,
                "semester_id": semester_id,
                "score": 77.5,
                "grade_rank": 4,
                "op": "INSERT",
            },
        )

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
            where="outbox_event_id = :e",
            params={"e": bad_event_id},
        )

        # Bad row should be marked processed_at so it doesn't replay forever.
        async with session_factory() as db:
            result = await db.execute(
                text("SELECT processed_at FROM public.outbox WHERE event_id = :e"),
                {"e": bad_event_id},
            )
            bad_processed_at = result.scalar_one()
    finally:
        await _stop_task(worker, cons_stop)
        await _stop_task(publisher, pub_stop)

    assert dlq_count == 1, f"poison row not dead-lettered (dlq={dlq_count})"
    assert bad_processed_at is not None, "poison row left unprocessed — would replay forever"
