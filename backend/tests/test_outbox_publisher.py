"""SMS-52: outbox-publisher worker — drain + catch-up + retry semantics."""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import pytest
from sqlalchemy import select

from app.models.outbox import Outbox
from app.services.outbox import fetch_unsent, mark_sent
from app.workers.outbox_publisher import _drain_once, run
from tests.conftest import async_session_test


class FakeProducer:
    """Records outbound messages; can be told to fail N times before succeeding."""

    def __init__(self, *, fail_first: int = 0):
        self.started = False
        self.stopped = False
        self.sent: list[tuple[str, bytes, bytes]] = []
        self._fail_remaining = fail_first

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def send_and_wait(self, topic: str, value: bytes, key: bytes | None = None):
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise RuntimeError("simulated broker down")
        self.sent.append((topic, value, key or b""))


async def _stage_outbox(n: int) -> list[int]:
    """Insert n unsent outbox rows; return their event_ids."""
    async with async_session_test() as session:
        ids: list[int] = []
        for i in range(n):
            row = Outbox(
                aggregate_type="grade",
                aggregate_id=uuid.uuid4(),
                topic="grade_events",
                payload={"i": i, "op": "INSERT"},
            )
            session.add(row)
            await session.flush()
            ids.append(row.event_id)
        await session.commit()
        return ids


@pytest.mark.asyncio
async def test_fetch_unsent_orders_by_event_id():
    await _stage_outbox(3)
    async with async_session_test() as session:
        rows = await fetch_unsent(session, limit=10)
    assert len(rows) == 3
    assert [r.event_id for r in rows] == sorted(r.event_id for r in rows)


@pytest.mark.asyncio
async def test_mark_sent_populates_sent_at():
    ids = await _stage_outbox(2)
    async with async_session_test() as session:
        updated = await mark_sent(session, ids)
    assert updated == 2

    async with async_session_test() as session:
        rows = (await session.execute(select(Outbox))).scalars().all()
    assert all(r.sent_at is not None for r in rows)
    # fetch_unsent should now return nothing
    async with async_session_test() as session:
        assert await fetch_unsent(session) == []


@pytest.mark.asyncio
async def test_drain_once_publishes_and_marks_sent():
    await _stage_outbox(3)
    producer = FakeProducer()
    async with async_session_test() as session:
        n = await _drain_once(session, producer, batch_size=10)

    assert n == 3
    assert len(producer.sent) == 3
    # payload is JSON-encoded
    topics = {topic for topic, _, _ in producer.sent}
    assert topics == {"grade_events"}
    payloads = [json.loads(value.decode("utf-8")) for _, value, _ in producer.sent]
    assert [p["i"] for p in payloads] == [0, 1, 2]

    async with async_session_test() as session:
        assert await fetch_unsent(session) == []


@pytest.mark.asyncio
async def test_drain_once_envelopes_event_id_into_payload():
    """Consumers (analytics-worker / SMS-53) dedupe on payload.event_id —
    the publisher must inject the outbox row's event_id into each message."""
    ids = await _stage_outbox(2)
    producer = FakeProducer()
    async with async_session_test() as session:
        await _drain_once(session, producer, batch_size=10)

    payloads = [json.loads(value.decode("utf-8")) for _, value, _ in producer.sent]
    assert [p["event_id"] for p in payloads] == ids


@pytest.mark.asyncio
async def test_drain_once_empty_outbox_returns_zero():
    producer = FakeProducer()
    async with async_session_test() as session:
        n = await _drain_once(session, producer)
    assert n == 0
    assert producer.sent == []


@pytest.mark.asyncio
async def test_drain_once_stops_on_publish_failure():
    """If send_and_wait raises mid-batch, only the rows already sent get marked."""
    await _stage_outbox(5)
    producer = FakeProducer(fail_first=0)

    # Patch to fail on the 3rd call
    real_send = producer.send_and_wait
    call_count = 0

    async def flaky_send(topic, value, key=None):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            raise RuntimeError("broker hiccup")
        await real_send(topic, value, key)

    producer.send_and_wait = flaky_send  # type: ignore[assignment]

    async with async_session_test() as session:
        n = await _drain_once(session, producer, batch_size=10)
    assert n == 2  # rows 0 and 1 got through; failure on row 2 stopped the batch

    async with async_session_test() as session:
        unsent = await fetch_unsent(session)
    assert len(unsent) == 3  # rows 2, 3, 4 still unsent — will be retried


@pytest.mark.asyncio
async def test_run_loop_catches_up_after_simulated_outage():
    """Stage rows, run the loop briefly with a producer that fails the first 3
    sends, and verify all rows eventually get published."""
    await _stage_outbox(5)
    producer = FakeProducer(fail_first=3)

    stop = asyncio.Event()

    async def stopper():
        await asyncio.sleep(0.5)
        stop.set()

    asyncio.create_task(stopper())

    # Use a no-op session_factory wrapper that points to our test session
    from tests.conftest import async_session_test as test_session_factory  # noqa: PLC0415

    await run(
        producer=producer,
        session_factory=test_session_factory,
        poll_interval_idle=0.05,
        backoff_initial=0.05,
        backoff_max=0.1,
        stop_event=stop,
    )

    # All 5 rows should have been published despite 3 initial failures
    async with async_session_test() as session:
        unsent = await fetch_unsent(session)
    assert unsent == []
    assert len(producer.sent) == 5
    assert producer.started is True
    assert producer.stopped is True


def _silence_unused_imports() -> None:
    _ = Any
