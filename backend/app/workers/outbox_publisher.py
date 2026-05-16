"""Outbox publisher — polls public.outbox and forwards rows to Kafka.

Per Design Spec §9.4 and ADR-002. Runs as its own container; on boot, the
`WHERE sent_at IS NULL` query naturally catches up any rows the previous
instance failed to publish (no separate replay logic needed).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.services.outbox import fetch_unsent, mark_sent


logger = logging.getLogger(__name__)


class Producer(Protocol):
    """Subset of AIOKafkaProducer we use — eases unit testing."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send_and_wait(self, topic: str, value: bytes, key: bytes | None = None): ...


async def _drain_once(db: AsyncSession, producer: Producer, *, batch_size: int = 100) -> int:
    """Publish one batch of unsent rows. Returns the number of rows marked sent.

    Each row is published individually before being marked sent. If `send_and_wait`
    raises (broker down, etc.), the row is left as-is and will be retried on the
    next loop iteration — no rows are silently dropped.
    """
    rows = await fetch_unsent(db, limit=batch_size)
    if not rows:
        return 0

    published_ids: list[int] = []
    for row in rows:
        try:
            # Inject the outbox event_id so downstream consumers can dedupe
            # on retries (see analytics-worker / SMS-53).
            envelope = {**row.payload, "event_id": row.event_id}
            await producer.send_and_wait(
                row.topic,
                value=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
                key=str(row.aggregate_id).encode("utf-8"),
            )
        except Exception as exc:  # broker error / network / serialization
            logger.warning("publish failed for event_id=%s: %s", row.event_id, exc)
            break  # stop the batch — let the next iteration retry from this row
        published_ids.append(row.event_id)

    if published_ids:
        await mark_sent(db, published_ids)
    return len(published_ids)


async def run(
    *,
    producer: Producer,
    session_factory: async_sessionmaker[AsyncSession],
    poll_interval_idle: float = 0.5,
    backoff_initial: float = 1.0,
    backoff_max: float = 30.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run the publisher loop until stop_event is set.

    Empty-poll waits `poll_interval_idle` (default 500ms) so the worker stays
    cheap when the outbox is drained. On consecutive errors, falls back to
    exponential backoff capped at `backoff_max` to avoid hammering a sick broker.
    """
    await producer.start()
    backoff = backoff_initial
    try:
        while stop_event is None or not stop_event.is_set():
            try:
                async with session_factory() as db:
                    n = await _drain_once(db, producer)
            except Exception:
                logger.exception("publisher iteration crashed; backing off %.1fs", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, backoff_max)
                continue

            if n == 0:
                backoff = backoff_initial
                await asyncio.sleep(poll_interval_idle)
            else:
                backoff = backoff_initial  # progress made — reset
    finally:
        await producer.stop()


def _build_default_producer() -> Producer:
    from aiokafka import AIOKafkaProducer  # imported here to keep test runs cheap

    return AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        enable_idempotence=True,
        acks="all",
    )


async def main() -> None:  # pragma: no cover — entrypoint
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    producer = _build_default_producer()
    try:
        await run(producer=producer, session_factory=session_factory)
    finally:
        await engine.dispose()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
