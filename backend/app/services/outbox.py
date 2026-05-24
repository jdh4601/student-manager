"""Outbox helpers shared between routers, publisher, and analytics-worker.

Per ADR-003. Two state-machine flags coordinate the pipeline:

- ``sent_at``      → publisher has emitted the NOTIFY (relay complete)
- ``processed_at`` → worker has projected the event into ``analytics.*``

Each of ``fetch_unsent_locked`` / ``claim_outbox_row`` uses
``SELECT ... FOR UPDATE SKIP LOCKED`` so multiple worker instances cooperate
without duplicating work — the Postgres equivalent of a Kafka consumer group's
partition assignment.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import Outbox


async def fetch_unsent(db: AsyncSession, *, limit: int = 100) -> list[Outbox]:
    """Return the oldest unsent outbox rows, ordered by event_id ascending.

    Plain (non-locking) read — used by unit tests and inspection paths.
    """
    stmt = (
        select(Outbox)
        .where(Outbox.sent_at.is_(None))
        .order_by(Outbox.event_id)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def fetch_unsent_locked(db: AsyncSession, *, limit: int = 100) -> list[Outbox]:
    """Lock and return the oldest unsent rows — publisher's batch fetch.

    Caller must hold an open transaction; the locks release on commit/rollback.
    SKIP LOCKED lets a second publisher instance race the first without blocking.
    """
    stmt = (
        select(Outbox)
        .where(Outbox.sent_at.is_(None))
        .order_by(Outbox.event_id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def fetch_unprocessed_locked(
    db: AsyncSession, *, limit: int = 100
) -> list[Outbox]:
    """Lock and return rows the publisher relayed but no worker has consumed.

    Used by worker boot-time catch-up to drain whatever piled up while the
    worker was offline. SKIP LOCKED + per-batch commit keeps scale=N safe.
    """
    stmt = (
        select(Outbox)
        .where(Outbox.sent_at.is_not(None), Outbox.processed_at.is_(None))
        .order_by(Outbox.event_id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def claim_outbox_row(db: AsyncSession, event_id: int) -> Outbox | None:
    """Lock one outbox row for processing — worker's per-NOTIFY claim.

    Returns the row only if it's still claimable (sent_at NOT NULL, processed_at NULL).
    If another worker already holds the lock, ``SKIP LOCKED`` returns no row and
    this returns ``None`` so the caller can move on cleanly.
    """
    stmt = (
        select(Outbox)
        .where(
            Outbox.event_id == event_id,
            Outbox.sent_at.is_not(None),
            Outbox.processed_at.is_(None),
        )
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def mark_sent(db: AsyncSession, event_ids: Iterable[int]) -> int:
    """Set sent_at = now() for the given event_ids; returns rows updated."""
    ids = list(event_ids)
    if not ids:
        return 0
    stmt = (
        update(Outbox)
        .where(Outbox.event_id.in_(ids))
        .values(sent_at=datetime.utcnow())
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0


async def mark_processed(db: AsyncSession, event_id: int) -> None:
    """Set processed_at = now() for one event_id. Caller commits."""
    stmt = (
        update(Outbox)
        .where(Outbox.event_id == event_id)
        .values(processed_at=datetime.utcnow())
    )
    await db.execute(stmt)


async def record_failure(
    db: AsyncSession, event_id: int, error: str
) -> int:
    """Bump retry_count, record last_error. Caller commits.

    Returns the new retry_count so callers can decide whether to dead-letter.
    """
    stmt = (
        update(Outbox)
        .where(Outbox.event_id == event_id)
        .values(
            retry_count=Outbox.retry_count + 1,
            last_error=error[:2000],  # cap to keep table small
        )
        .returning(Outbox.retry_count)
    )
    result = await db.execute(stmt)
    row = result.first()
    return int(row[0]) if row else 0


async def emit_notify(db: AsyncSession, *, channel: str, payload: str) -> None:
    """Emit Postgres NOTIFY on ``channel`` with the given payload.

    Uses ``pg_notify($1, $2)`` so the channel/payload bind safely as parameters
    (raw ``NOTIFY name, 'text'`` does not allow parameterised payloads).
    Channel names are constrained to the 4 known event topics by the publisher,
    so identifier injection is not a concern in practice.
    """
    await db.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": channel, "payload": payload},
    )
