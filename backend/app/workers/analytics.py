"""Analytics worker — consumes outbox events via Postgres LISTEN/NOTIFY and
projects them into the analytics schema (fact + agg tables).

Per Design Spec §9.5 and ADR-003 (supersedes ADR-002):

- Channels: ``grade_events`` / ``attendance_events`` / ``feedback_events`` /
  ``counseling_events`` — one NOTIFY per outbox row, emitted by the publisher.
- Cooperative scale-out: every running worker LISTENs to every channel, but
  ``SELECT ... FOR UPDATE SKIP LOCKED`` on the outbox row ensures only one
  worker claims each event. ``scale=N`` distributes work the way a Kafka
  consumer group's partition assignment would.
- Catch-up: on boot — and on a 60s timer to defend against missed NOTIFY
  (connection blip, payload >8KB) — the worker drains ``WHERE processed_at
  IS NULL`` using the same SKIP LOCKED claim.

Idempotency
-----------
The outbox row's ``event_id`` is the primary key for ``analytics.fact_*``
(``INSERT ... ON CONFLICT (event_id) DO NOTHING``). Combined with the
``processed_at`` mark, replays from boot-time catch-up are no-ops.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.outbox import Outbox
from app.services.outbox import (
    claim_outbox_row,
    fetch_unprocessed_locked,
    mark_processed,
    record_failure,
)


logger = logging.getLogger(__name__)


GRADE_EVENTS_TOPIC = "grade_events"
ATTENDANCE_EVENTS_TOPIC = "attendance_events"
FEEDBACK_EVENTS_TOPIC = "feedback_events"
COUNSELING_EVENTS_TOPIC = "counseling_events"
SUBSCRIBED_CHANNELS = (
    GRADE_EVENTS_TOPIC,
    ATTENDANCE_EVENTS_TOPIC,
    FEEDBACK_EVENTS_TOPIC,
    COUNSELING_EVENTS_TOPIC,
)


class PoisonMessageError(Exception):
    """A message is permanently unprocessable — malformed payload, missing
    required fields, or an unknown topic. The worker routes the outbox row
    to ``analytics.dead_letter_event`` and marks ``processed_at`` so it
    stops blocking the queue."""


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

REQUIRED_FEEDBACK_PAYLOAD_FIELDS = (
    "event_id",
    "feedback_id",
    "student_id",
    "semester_id",
    "op",
)

REQUIRED_COUNSELING_PAYLOAD_FIELDS = (
    "event_id",
    "counseling_id",
    "student_id",
    "teacher_id",
    "date",
    "op",
)


class AnalyticsRepository(Protocol):
    """Operations the worker needs against the analytics schema.

    Splitting the SQL behind this protocol keeps the consumer logic testable
    without a running Postgres — see tests/workers/test_analytics_consumer.py
    for the in-memory fake.
    """

    async def insert_fact_event(self, *, event_id: int, payload: dict) -> bool:
        """Insert one row into ``analytics.fact_grade_event``.

        Returns ``True`` if a new row was inserted, ``False`` if the event_id
        already existed (ON CONFLICT DO NOTHING). The caller uses this to skip
        the agg recompute on retried messages.
        """

    async def insert_fact_attendance(self, *, event_id: int, payload: dict) -> bool:
        """Insert one row into ``analytics.fact_attendance_event`` (idempotent on event_id)."""

    async def insert_fact_feedback(self, *, event_id: int, payload: dict) -> bool:
        """Insert one row into ``analytics.fact_feedback_event`` (idempotent on event_id)."""

    async def insert_fact_counseling(self, *, event_id: int, payload: dict) -> bool:
        """Insert one row into ``analytics.fact_counseling_event`` (idempotent on event_id).

        Counseling has no aggregate projection — this fact row is for
        audit / future BI use only.
        """

    async def record_dead_letter(
        self,
        *,
        outbox_event_id: int,
        topic: str,
        raw_value: bytes,
        error: str,
    ) -> None:
        """Persist a poison message into ``analytics.dead_letter_event``."""

    async def recompute_agg_subject(
        self, *, student_id: str, subject_id: str, semester_id: str
    ) -> None:
        """UPSERT ``analytics.agg_student_subject`` for the (student, subject, semester) key."""

    async def recompute_agg_overall(self, *, student_id: str, semester_id: str) -> None:
        """UPSERT ``analytics.agg_student_overall`` for the (student, semester) key."""


def _normalize_payload(row: Outbox) -> dict[str, Any]:
    """Build the dispatch payload for one outbox row.

    The publisher only emits ``{"event_id": <id>}`` over NOTIFY (8KB limit);
    the full payload lives on the row itself. ``event_id`` is injected so
    dispatch handlers can populate ``analytics.fact_*.event_id``.
    """
    if not isinstance(row.payload, dict):
        raise ValueError(
            f"outbox.payload must be JSON object, got {type(row.payload).__name__}"
        )
    return {**row.payload, "event_id": row.event_id}


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
    """Apply one attendance_events payload to the analytics schema."""
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


async def process_feedback_event(payload: dict, *, repo: AnalyticsRepository) -> None:
    """Apply one feedback_events payload to the analytics schema."""
    for field_name in REQUIRED_FEEDBACK_PAYLOAD_FIELDS:
        if field_name not in payload:
            raise KeyError(
                f"feedback_events payload missing required field: {field_name}"
            )

    event_id = int(payload["event_id"])
    inserted = await repo.insert_fact_feedback(event_id=event_id, payload=payload)
    if not inserted:
        logger.debug(
            "event_id=%s already in fact_feedback_event — skipping recompute", event_id
        )
        return

    await repo.recompute_agg_overall(
        student_id=payload["student_id"], semester_id=payload["semester_id"]
    )


async def process_counseling_event(payload: dict, *, repo: AnalyticsRepository) -> None:
    """Apply one counseling_events payload to the analytics schema.

    Counseling has no aggregate projection (Design Spec §9.1) — we only
    store the fact row for audit / future BI. INSERT is idempotent on event_id.
    """
    for field_name in REQUIRED_COUNSELING_PAYLOAD_FIELDS:
        if field_name not in payload:
            raise KeyError(
                f"counseling_events payload missing required field: {field_name}"
            )

    event_id = int(payload["event_id"])
    await repo.insert_fact_counseling(event_id=event_id, payload=payload)


async def dispatch_event(payload: dict, *, repo: AnalyticsRepository, topic: str) -> None:
    """Route a payload to the right per-channel handler."""
    if topic == GRADE_EVENTS_TOPIC:
        await process_event(payload, repo=repo)
    elif topic == ATTENDANCE_EVENTS_TOPIC:
        await process_attendance_event(payload, repo=repo)
    elif topic == FEEDBACK_EVENTS_TOPIC:
        await process_feedback_event(payload, repo=repo)
    elif topic == COUNSELING_EVENTS_TOPIC:
        await process_counseling_event(payload, repo=repo)
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
        from datetime import date as _date
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
                "date": _date.fromisoformat(payload["date"]),
                "status": payload["status"],
                "op": payload["op"],
            },
        )
        return (result.rowcount or 0) > 0

    async def insert_fact_feedback(self, *, event_id: int, payload: dict) -> bool:
        from sqlalchemy import text

        stmt = text(
            """
            INSERT INTO analytics.fact_feedback_event
                (event_id, feedback_id, student_id, semester_id,
                 category, op, occurred_at)
            VALUES
                (:event_id, :feedback_id, :student_id, :semester_id,
                 :category, :op, now())
            ON CONFLICT (event_id) DO NOTHING
            """
        )
        result = await self._db.execute(
            stmt,
            {
                "event_id": event_id,
                "feedback_id": payload["feedback_id"],
                "student_id": payload["student_id"],
                "semester_id": payload["semester_id"],
                "category": payload.get("category"),
                "op": payload["op"],
            },
        )
        return (result.rowcount or 0) > 0

    async def insert_fact_counseling(self, *, event_id: int, payload: dict) -> bool:
        from datetime import date as _date
        from sqlalchemy import text

        stmt = text(
            """
            INSERT INTO analytics.fact_counseling_event
                (event_id, counseling_id, student_id, teacher_id,
                 date, op, occurred_at)
            VALUES
                (:event_id, :counseling_id, :student_id, :teacher_id,
                 :date, :op, now())
            ON CONFLICT (event_id) DO NOTHING
            """
        )
        result = await self._db.execute(
            stmt,
            {
                "event_id": event_id,
                "counseling_id": payload["counseling_id"],
                "student_id": payload["student_id"],
                "teacher_id": payload["teacher_id"],
                "date": _date.fromisoformat(payload["date"]),
                "op": payload["op"],
            },
        )
        return (result.rowcount or 0) > 0

    async def record_dead_letter(
        self,
        *,
        outbox_event_id: int,
        topic: str,
        raw_value: bytes,
        error: str,
    ) -> None:
        from sqlalchemy import text

        stmt = text(
            """
            INSERT INTO analytics.dead_letter_event
                (topic, outbox_event_id, raw_value, error, occurred_at)
            VALUES (:topic, :outbox_event_id, :raw_value, :error, now())
            """
        )
        await self._db.execute(
            stmt,
            {
                "topic": topic,
                "outbox_event_id": outbox_event_id,
                "raw_value": raw_value,
                "error": error,
            },
        )

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
        """Recompute every ``agg_student_overall`` column from the current fact state."""
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
            ),
            latest_feedback AS (
                SELECT DISTINCT ON (feedback_id)
                    feedback_id, op
                FROM analytics.fact_feedback_event
                WHERE student_id = :student_id
                  AND semester_id = :semester_id
                ORDER BY feedback_id, occurred_at DESC, event_id DESC
            ),
            feedback_stats AS (
                SELECT count(*) FILTER (WHERE op != 'DELETE')::int AS feedback_count
                FROM latest_feedback
            )
            INSERT INTO analytics.agg_student_overall
                (student_id, semester_id,
                 total_score, avg_score, subject_count,
                 attendance_present_rate, feedback_count, refreshed_at)
            SELECT
                :student_id, :semester_id,
                gs.total_score, gs.avg_score, COALESCE(gs.subject_count, 0),
                ats.present_rate,
                COALESCE(fs.feedback_count, 0),
                now()
            FROM grade_stats gs
            CROSS JOIN attendance_stats ats
            CROSS JOIN feedback_stats fs
            ON CONFLICT (student_id, semester_id) DO UPDATE SET
                total_score             = EXCLUDED.total_score,
                avg_score               = EXCLUDED.avg_score,
                subject_count           = EXCLUDED.subject_count,
                attendance_present_rate = EXCLUDED.attendance_present_rate,
                feedback_count          = EXCLUDED.feedback_count,
                refreshed_at            = EXCLUDED.refreshed_at
            """
        )
        await self._db.execute(
            stmt,
            {"student_id": student_id, "semester_id": semester_id},
        )


class Listener(Protocol):
    """Subset of an asyncpg LISTEN connection we use — eases unit testing."""

    async def add_listener(self, channel: str, callback: Callable[..., Any]) -> None: ...
    async def remove_listener(self, channel: str, callback: Callable[..., Any]) -> None: ...
    async def close(self) -> None: ...


async def _process_one(
    event_id: int,
    *,
    topic: str | None,
    session_factory: async_sessionmaker[AsyncSession],
    repo_builder: Callable[[AsyncSession], AnalyticsRepository],
    max_retries: int,
) -> None:
    """Claim a single outbox row, dispatch it, and mark terminal state.

    The whole thing runs in one DB transaction so the SKIP LOCKED claim and
    the ``processed_at`` mark commit atomically — if processing crashes, the
    row stays unclaimed for the next worker to retry.
    """
    async with session_factory() as db:
        async with db.begin():
            row = await claim_outbox_row(db, event_id)
            if row is None:
                # Either: (a) another worker already claimed it, or
                # (b) it was already processed. Either way, nothing to do.
                return

            channel = topic or row.topic
            try:
                payload = _normalize_payload(row)
            except (KeyError, ValueError) as exc:
                await _dead_letter(
                    db, row, channel, str(exc), repo_builder=repo_builder
                )
                await mark_processed(db, row.event_id)
                return

            repo = repo_builder(db)
            try:
                await dispatch_event(payload, repo=repo, topic=channel)
            except (KeyError, ValueError) as exc:
                # Permanent: the schema is wrong. Dead-letter immediately.
                await _dead_letter(
                    db, row, channel, f"dispatch failed: {exc}", repo_builder=repo_builder
                )
                await mark_processed(db, row.event_id)
                return
            except Exception as exc:
                # Transient (DB blip, etc.) — bump retry, exhaust then dead-letter.
                new_count = await record_failure(db, row.event_id, str(exc))
                if new_count >= max_retries:
                    await _dead_letter(
                        db, row, channel,
                        f"max retries ({max_retries}) exceeded: {exc}",
                        repo_builder=repo_builder,
                    )
                    await mark_processed(db, row.event_id)
                    return
                # Re-raise so the transaction rolls back and the row stays
                # claimable for the next iteration.
                raise

            await mark_processed(db, row.event_id)


async def _dead_letter(
    db: AsyncSession,
    row: Outbox,
    topic: str,
    error: str,
    *,
    repo_builder: Callable[[AsyncSession], AnalyticsRepository],
) -> None:
    repo = repo_builder(db)
    raw = json.dumps({"event_id": row.event_id, "payload": row.payload}).encode("utf-8")
    await repo.record_dead_letter(
        outbox_event_id=row.event_id,
        topic=topic,
        raw_value=raw,
        error=error,
    )


def _build_asyncpg_dsn(database_url: str) -> str:
    """Translate SQLAlchemy ``postgresql+asyncpg://...`` URL to a plain DSN."""
    # asyncpg.connect accepts `postgresql://...` but not `+asyncpg`.
    if database_url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + database_url[len("postgresql+asyncpg://"):]
    return database_url


async def run(
    *,
    listener: Listener,
    session_factory: async_sessionmaker[AsyncSession],
    repo_builder: Callable[[AsyncSession], AnalyticsRepository] | None = None,
    stop_event: asyncio.Event | None = None,
    catchup_interval: float | None = None,
    max_retries: int | None = None,
) -> None:
    """LISTEN loop — register handlers, drain backlog, then react to NOTIFYs.

    On every NOTIFY (or 60s catch-up tick), workers race for the outbox row
    via SKIP LOCKED; only one wins. A startup catch-up handles whatever
    accumulated while the worker was offline, and the periodic tick defends
    against missed NOTIFYs (connection blip, async backpressure, payload
    truncation).
    """
    if repo_builder is None:
        repo_builder = lambda db: PostgresAnalyticsRepo(db)  # noqa: E731

    catchup = catchup_interval if catchup_interval is not None else settings.listen_notify_catchup_interval
    retries = max_retries if max_retries is not None else settings.outbox_max_retries

    queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()

    def make_callback(channel: str) -> Callable[..., Any]:
        def _cb(connection: Any, pid: int, channel_name: str, payload: str) -> None:
            try:
                data = json.loads(payload) if payload else {}
                event_id = int(data.get("event_id"))
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning(
                    "ignoring malformed NOTIFY payload on channel=%s: %r",
                    channel_name,
                    payload,
                )
                return
            queue.put_nowait((channel, event_id))
        return _cb

    callbacks: dict[str, Callable[..., Any]] = {}
    for channel in SUBSCRIBED_CHANNELS:
        cb = make_callback(channel)
        callbacks[channel] = cb
        await listener.add_listener(channel, cb)

    async def catchup_loop() -> None:
        """Periodic + boot-time drain — handles missed NOTIFYs and prior backlog."""
        while stop_event is None or not stop_event.is_set():
            try:
                async with session_factory() as db:
                    async with db.begin():
                        rows = await fetch_unprocessed_locked(db, limit=200)
                    # Release the lock before queueing so workers in this same
                    # process don't double-claim — _process_one re-claims with
                    # its own SKIP LOCKED inside a fresh transaction.
                    for row in rows:
                        queue.put_nowait((row.topic, row.event_id))
                if rows:
                    logger.info("catch-up drained %d backlog row(s)", len(rows))
            except Exception:
                logger.exception("catch-up iteration failed; will retry next tick")
            try:
                await asyncio.wait_for(
                    stop_event.wait() if stop_event else asyncio.Event().wait(),
                    timeout=catchup,
                )
            except asyncio.TimeoutError:
                continue

    catchup_task = asyncio.create_task(catchup_loop())

    try:
        while stop_event is None or not stop_event.is_set():
            try:
                topic, event_id = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            try:
                await _process_one(
                    event_id,
                    topic=topic,
                    session_factory=session_factory,
                    repo_builder=repo_builder,
                    max_retries=retries,
                )
            except Exception:
                logger.exception(
                    "transient failure processing event_id=%s — will retry on next NOTIFY/catch-up",
                    event_id,
                )
    finally:
        catchup_task.cancel()
        try:
            await catchup_task
        except (asyncio.CancelledError, Exception):
            pass
        for channel, cb in callbacks.items():
            try:
                await listener.remove_listener(channel, cb)
            except Exception:
                logger.debug("listener.remove_listener(%s) failed during shutdown", channel)
        try:
            await listener.close()
        except Exception:
            logger.debug("listener.close() failed during shutdown")


async def _build_default_listener() -> Listener:  # pragma: no cover — entrypoint plumbing
    import asyncpg

    dsn = _build_asyncpg_dsn(settings.database_url)
    conn = await asyncpg.connect(dsn)
    return conn  # asyncpg.Connection satisfies the Listener Protocol


async def main() -> None:  # pragma: no cover — entrypoint
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    listener = await _build_default_listener()
    try:
        await run(listener=listener, session_factory=session_factory)
    finally:
        await engine.dispose()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
