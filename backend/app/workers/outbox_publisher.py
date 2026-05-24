"""Outbox publisher — polls public.outbox and emits a Postgres NOTIFY per row.

Per ADR-003 (supersedes ADR-002). The previous implementation produced records
to Kafka; this one emits ``SELECT pg_notify(<topic>, <payload>)`` and updates
``sent_at`` in the same transaction. ``SELECT FOR UPDATE SKIP LOCKED`` keeps
multiple publisher instances safe (single instance is the default deployment,
but the lock is cheap insurance).

The boot-time ``WHERE sent_at IS NULL`` query naturally catches up rows the
previous instance failed to publish — no separate replay logic needed.

The ``Notifier`` protocol exists so unit tests can inject a stub: ``pg_notify``
is Postgres-only, but the rest of the publisher (fetch + mark) works on SQLite
under the unit-test conftest.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Protocol

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.outbox import Outbox
from app.services.outbox import emit_notify, fetch_unsent_locked


logger = logging.getLogger(__name__)


class Notifier(Protocol):
    """Indirection over ``SELECT pg_notify(...)`` for testability."""

    async def notify(self, db: AsyncSession, *, channel: str, payload: str) -> None: ...


class PgNotifyNotifier:
    """Default implementation — emits ``SELECT pg_notify(:channel, :payload)``."""

    async def notify(self, db: AsyncSession, *, channel: str, payload: str) -> None:
        await emit_notify(db, channel=channel, payload=payload)


async def _drain_once(
    db: AsyncSession,
    notifier: Notifier,
    *,
    batch_size: int = 100,
) -> int:
    """Relay one batch of unsent outbox rows — returns rows relayed.

    Holds a single transaction across the fetch / notify / mark-sent so:
      1. SKIP LOCKED guarantees no other publisher touches the same rows
      2. If notify or mark_sent raises, the whole batch rolls back and the
         rows re-appear unsent on the next iteration
    """
    async with db.begin():
        rows = await fetch_unsent_locked(db, limit=batch_size)
        if not rows:
            return 0

        relayed_ids: list[int] = []
        for row in rows:
            # Tiny envelope: only the outbox event_id travels through NOTIFY
            # (8KB payload limit). Workers fetch the full payload from the
            # outbox row by id, so large grade payloads / counseling notes
            # ride safely.
            envelope = json.dumps({"event_id": row.event_id})
            try:
                await notifier.notify(db, channel=row.topic, payload=envelope)
            except Exception as exc:
                logger.warning(
                    "pg_notify failed for event_id=%s topic=%s: %s",
                    row.event_id,
                    row.topic,
                    exc,
                )
                # Abort the batch — transaction rollback releases SKIP LOCKED
                # so a retry from a fresh iteration can pick these up again.
                raise

            relayed_ids.append(row.event_id)

        if relayed_ids:
            await db.execute(
                update(Outbox)
                .where(Outbox.event_id.in_(relayed_ids))
                .values(sent_at=datetime.utcnow())
            )

    return len(relayed_ids)


async def run(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    notifier: Notifier | None = None,
    poll_interval_idle: float | None = None,
    backoff_initial: float = 1.0,
    backoff_max: float = 30.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run the publisher loop until ``stop_event`` is set.

    Empty-poll waits ``poll_interval_idle`` (default from settings: 500ms) so
    the worker stays cheap when the outbox is drained. On consecutive errors,
    falls back to exponential backoff capped at ``backoff_max`` so a sick
    database doesn't get hammered.
    """
    if notifier is None:
        notifier = PgNotifyNotifier()
    idle_wait = (
        poll_interval_idle
        if poll_interval_idle is not None
        else settings.listen_notify_idle_poll_interval
    )
    backoff = backoff_initial
    while stop_event is None or not stop_event.is_set():
        try:
            async with session_factory() as db:
                n = await _drain_once(db, notifier)
        except Exception:
            logger.exception("publisher iteration crashed; backing off %.1fs", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, backoff_max)
            continue

        if n == 0:
            backoff = backoff_initial
            await asyncio.sleep(idle_wait)
        else:
            backoff = backoff_initial  # progress made — reset


async def main() -> None:  # pragma: no cover — entrypoint
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await run(session_factory=session_factory)
    finally:
        await engine.dispose()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
