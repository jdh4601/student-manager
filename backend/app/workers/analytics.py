"""Analytics worker — consumes grade_events from Kafka and projects them into
the analytics schema (fact + agg tables).

Per Design Spec §9.5 and ADR-002:

- Kafka topic: ``grade_events`` (one record per grade INSERT/UPDATE)
- Consumer group: ``analytics-worker`` (single logical reader; partitions can
  scale horizontally later)
- ``enable_auto_commit=False`` — we commit only AFTER the DB transaction
  succeeds, so a crash mid-write replays the record on restart.

Idempotency
-----------
The outbox row's ``event_id`` is propagated by the publisher into the Kafka
payload. The consumer INSERTs into ``analytics.fact_grade_event`` with that
event_id as the primary key (``ON CONFLICT DO NOTHING``). A duplicate replay
becomes a no-op — the row count stays at 1, and the agg recompute is skipped
since nothing changed.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


logger = logging.getLogger(__name__)


GRADE_EVENTS_TOPIC = "grade_events"
ATTENDANCE_EVENTS_TOPIC = "attendance_events"
SUBSCRIBED_TOPICS = (GRADE_EVENTS_TOPIC, ATTENDANCE_EVENTS_TOPIC)
CONSUMER_GROUP_ID = "analytics-worker"


REQUIRED_PAYLOAD_FIELDS = (
    "event_id",
    "grade_id",
    "student_id",
    "subject_id",
    "semester_id",
    "op",
)

REQUIRED_ATTENDANCE_PAYLOAD_FIELDS = (
    "event_id",
    "attendance_id",
    "student_id",
    "semester_id",
    "date",
    "status",
    "op",
)


class AnalyticsRepository(Protocol):
    """Operations the consumer needs against the analytics schema.

    Splitting the SQL behind this protocol keeps the consumer logic testable
    without a running Postgres — see tests/workers/test_analytics_consumer.py
    for the in-memory fake.
    """

    async def insert_fact_event(self, *, event_id: int, payload: dict) -> bool:
        """Insert one row into analytics.fact_grade_event.

        Returns True if a new row was inserted, False if the event_id already
        existed (ON CONFLICT DO NOTHING). The caller uses this to skip the
        agg recompute on retried messages.
        """

    async def insert_fact_attendance(self, *, event_id: int, payload: dict) -> bool:
        """Insert one row into analytics.fact_attendance_event.

        Same semantics as ``insert_fact_event`` but for attendance — returns
        False on event_id conflict so the consumer can skip the recompute.
        """

    async def recompute_agg_subject(
        self, *, student_id: str, subject_id: str, semester_id: str
    ) -> None:
        """UPSERT analytics.agg_student_subject for the (student, subject, semester) key."""

    async def recompute_agg_overall(self, *, student_id: str, semester_id: str) -> None:
        """UPSERT analytics.agg_student_overall for the (student, semester) key."""


def decode_record(value: bytes) -> dict:
    """Decode a Kafka record value into a payload dict.

    Anything other than a JSON object is a producer bug — raise so the consumer
    leaves the offset uncommitted and an operator can investigate.
    """
    obj = json.loads(value.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"expected JSON object, got {type(obj).__name__}")
    return obj


async def process_event(payload: dict, *, repo: AnalyticsRepository) -> None:
    """Apply one grade_events payload to the analytics schema.

    Order matters: fact INSERT first, then agg recompute. If the fact insert
    is a no-op (ON CONFLICT), the recompute is skipped — the existing aggs
    already reflect this event from the first time it was processed.
    """
    for field_name in REQUIRED_PAYLOAD_FIELDS:
        if field_name not in payload:
            raise KeyError(f"grade_events payload missing required field: {field_name}")

    event_id = int(payload["event_id"])
    inserted = await repo.insert_fact_event(event_id=event_id, payload=payload)
    if not inserted:
        logger.debug("event_id=%s already in fact_grade_event — skipping recompute", event_id)
        return

    student_id = payload["student_id"]
    subject_id = payload["subject_id"]
    semester_id = payload["semester_id"]
    await repo.recompute_agg_subject(
        student_id=student_id, subject_id=subject_id, semester_id=semester_id
    )
    await repo.recompute_agg_overall(student_id=student_id, semester_id=semester_id)


async def process_attendance_event(payload: dict, *, repo: AnalyticsRepository) -> None:
    """Apply one attendance_events payload to the analytics schema.

    Attendance only touches agg_student_overall.attendance_present_rate —
    there is no per-subject aggregation for attendance.
    """
    for field_name in REQUIRED_ATTENDANCE_PAYLOAD_FIELDS:
        if field_name not in payload:
            raise KeyError(
                f"attendance_events payload missing required field: {field_name}"
            )

    event_id = int(payload["event_id"])
    inserted = await repo.insert_fact_attendance(event_id=event_id, payload=payload)
    if not inserted:
        logger.debug(
            "event_id=%s already in fact_attendance_event — skipping recompute", event_id
        )
        return

    await repo.recompute_agg_overall(
        student_id=payload["student_id"], semester_id=payload["semester_id"]
    )


async def dispatch_event(payload: dict, *, repo: AnalyticsRepository, topic: str) -> None:
    """Route a Kafka record to the right per-topic handler."""
    if topic == GRADE_EVENTS_TOPIC:
        await process_event(payload, repo=repo)
    elif topic == ATTENDANCE_EVENTS_TOPIC:
        await process_attendance_event(payload, repo=repo)
    else:
        raise ValueError(f"no handler registered for topic={topic!r}")


class PostgresAnalyticsRepo:
    """Postgres-backed implementation using raw SQL against the analytics schema.

    The aggregate recomputes use ``DISTINCT ON (grade_id) ... ORDER BY occurred_at DESC``
    to dedupe historical events down to the latest state per grade_id before
    averaging. This keeps UPDATE events from double-counting.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def insert_fact_event(self, *, event_id: int, payload: dict) -> bool:
        from sqlalchemy import text

        stmt = text(
            """
            INSERT INTO analytics.fact_grade_event
                (event_id, grade_id, student_id, subject_id, semester_id,
                 score, grade_rank, op, occurred_at)
            VALUES
                (:event_id, :grade_id, :student_id, :subject_id, :semester_id,
                 :score, :grade_rank, :op, now())
            ON CONFLICT (event_id) DO NOTHING
            """
        )
        result = await self._db.execute(
            stmt,
            {
                "event_id": event_id,
                "grade_id": payload["grade_id"],
                "student_id": payload["student_id"],
                "subject_id": payload["subject_id"],
                "semester_id": payload["semester_id"],
                "score": payload.get("score"),
                "grade_rank": payload.get("grade_rank"),
                "op": payload["op"],
            },
        )
        return (result.rowcount or 0) > 0

    async def insert_fact_attendance(self, *, event_id: int, payload: dict) -> bool:
        from sqlalchemy import text

        stmt = text(
            """
            INSERT INTO analytics.fact_attendance_event
                (event_id, attendance_id, student_id, semester_id,
                 date, status, op, occurred_at)
            VALUES
                (:event_id, :attendance_id, :student_id, :semester_id,
                 :date, :status, :op, now())
            ON CONFLICT (event_id) DO NOTHING
            """
        )
        result = await self._db.execute(
            stmt,
            {
                "event_id": event_id,
                "attendance_id": payload["attendance_id"],
                "student_id": payload["student_id"],
                "semester_id": payload["semester_id"],
                "date": payload["date"],
                "status": payload["status"],
                "op": payload["op"],
            },
        )
        return (result.rowcount or 0) > 0

    async def recompute_agg_subject(
        self, *, student_id: str, subject_id: str, semester_id: str
    ) -> None:
        from sqlalchemy import text

        stmt = text(
            """
            WITH latest AS (
                SELECT DISTINCT ON (grade_id)
                    grade_id, score, grade_rank, op
                FROM analytics.fact_grade_event
                WHERE student_id = :student_id
                  AND subject_id = :subject_id
                  AND semester_id = :semester_id
                ORDER BY grade_id, occurred_at DESC, event_id DESC
            ),
            stats AS (
                SELECT
                    avg(score)         AS avg_score,
                    max(score)         AS max_score,
                    min(score)         AS min_score,
                    -- latest_rank: rank from the most-recent event across the set
                    (SELECT grade_rank FROM latest
                       ORDER BY grade_rank IS NULL, grade_rank
                       LIMIT 1)        AS latest_rank,
                    count(*)::int      AS sample_count
                FROM latest
                WHERE score IS NOT NULL
            )
            INSERT INTO analytics.agg_student_subject
                (student_id, subject_id, semester_id,
                 avg_score, max_score, min_score, latest_rank, sample_count, refreshed_at)
            SELECT
                :student_id, :subject_id, :semester_id,
                avg_score, max_score, min_score, latest_rank,
                COALESCE(sample_count, 0), now()
            FROM stats
            ON CONFLICT (student_id, subject_id, semester_id) DO UPDATE SET
                avg_score    = EXCLUDED.avg_score,
                max_score    = EXCLUDED.max_score,
                min_score    = EXCLUDED.min_score,
                latest_rank  = EXCLUDED.latest_rank,
                sample_count = EXCLUDED.sample_count,
                refreshed_at = EXCLUDED.refreshed_at
            """
        )
        await self._db.execute(
            stmt,
            {
                "student_id": student_id,
                "subject_id": subject_id,
                "semester_id": semester_id,
            },
        )

    async def recompute_agg_overall(self, *, student_id: str, semester_id: str) -> None:
        """Recompute every agg_student_overall column from the current fact state.

        We always recompute total/avg/subject_count (from fact_grade_event) AND
        attendance_present_rate (from fact_attendance_event) in the same UPSERT,
        regardless of which event triggered the call. This keeps a single
        consistent UPSERT path for both grade and attendance consumers.
        """
        from sqlalchemy import text

        stmt = text(
            """
            WITH latest_grades AS (
                SELECT DISTINCT ON (grade_id)
                    grade_id, subject_id, score
                FROM analytics.fact_grade_event
                WHERE student_id = :student_id
                  AND semester_id = :semester_id
                ORDER BY grade_id, occurred_at DESC, event_id DESC
            ),
            grade_stats AS (
                SELECT
                    sum(score)                            AS total_score,
                    avg(score)                            AS avg_score,
                    count(DISTINCT subject_id)::int       AS subject_count
                FROM latest_grades
                WHERE score IS NOT NULL
            ),
            latest_attendance AS (
                SELECT DISTINCT ON (attendance_id)
                    attendance_id, status
                FROM analytics.fact_attendance_event
                WHERE student_id = :student_id
                  AND semester_id = :semester_id
                ORDER BY attendance_id, occurred_at DESC, event_id DESC
            ),
            attendance_stats AS (
                SELECT
                    CASE WHEN count(*) > 0
                         THEN ROUND(
                              count(*) FILTER (WHERE status = 'present')::numeric
                              / count(*)::numeric, 3)
                         ELSE NULL
                    END AS present_rate
                FROM latest_attendance
            )
            INSERT INTO analytics.agg_student_overall
                (student_id, semester_id,
                 total_score, avg_score, subject_count,
                 attendance_present_rate, refreshed_at)
            SELECT
                :student_id, :semester_id,
                gs.total_score, gs.avg_score, COALESCE(gs.subject_count, 0),
                ats.present_rate, now()
            FROM grade_stats gs CROSS JOIN attendance_stats ats
            ON CONFLICT (student_id, semester_id) DO UPDATE SET
                total_score             = EXCLUDED.total_score,
                avg_score               = EXCLUDED.avg_score,
                subject_count           = EXCLUDED.subject_count,
                attendance_present_rate = EXCLUDED.attendance_present_rate,
                refreshed_at            = EXCLUDED.refreshed_at
            """
        )
        await self._db.execute(
            stmt,
            {"student_id": student_id, "semester_id": semester_id},
        )


class Consumer(Protocol):
    """Subset of AIOKafkaConsumer we use — eases unit testing."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def getone(self) -> Any: ...
    async def commit(self) -> None: ...


async def run(
    *,
    consumer: Consumer,
    session_factory: async_sessionmaker[AsyncSession],
    repo_builder: Callable[[AsyncSession], AnalyticsRepository] | None = None,
    stop_event: asyncio.Event | None = None,
    backoff_initial: float = 1.0,
    backoff_max: float = 30.0,
    getone_timeout: float = 1.0,
) -> None:
    """Consumer loop — fetch one record, process in a fresh DB TX, commit offset.

    ``getone_timeout`` lets the loop wake periodically to check ``stop_event``
    even when the broker is idle; the call is wrapped in ``wait_for`` so we
    don't block shutdown indefinitely.
    """
    if repo_builder is None:
        repo_builder = lambda db: PostgresAnalyticsRepo(db)  # noqa: E731

    await consumer.start()
    backoff = backoff_initial
    try:
        while stop_event is None or not stop_event.is_set():
            try:
                record = await asyncio.wait_for(consumer.getone(), timeout=getone_timeout)
            except asyncio.TimeoutError:
                continue
            except Exception:
                logger.exception("consumer.getone() failed; backing off %.1fs", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, backoff_max)
                continue

            try:
                payload = decode_record(record.value)
                async with session_factory() as db:
                    repo = repo_builder(db)
                    await dispatch_event(payload, repo=repo, topic=record.topic)
                    await db.commit()
                await consumer.commit()
                backoff = backoff_initial
            except Exception:
                logger.exception(
                    "failed to process record offset=%s — offset will not be committed",
                    getattr(record, "offset", "?"),
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, backoff_max)
    finally:
        await consumer.stop()


def _build_default_consumer() -> Consumer:
    from aiokafka import AIOKafkaConsumer  # imported here to keep test runs cheap

    return AIOKafkaConsumer(
        *SUBSCRIBED_TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=CONSUMER_GROUP_ID,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )


async def main() -> None:  # pragma: no cover — entrypoint
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    consumer = _build_default_consumer()
    try:
        await run(consumer=consumer, session_factory=session_factory)
    finally:
        await engine.dispose()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
