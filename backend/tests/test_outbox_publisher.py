"""outbox-publisher — drain + catch-up + retry semantics (post ADR-003)."""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import Outbox
from app.services.outbox import fetch_unsent, mark_sent
from app.workers.outbox_publisher import _drain_once, run
from tests.conftest import async_session_test


class FakeNotifier:
    """Records NOTIFY calls; can be told to fail N times before succeeding."""

    def __init__(self, *, fail_first: int = 0):
        self.sent: list[tuple[str, str]] = []
        self._fail_remaining = fail_first

    async def notify(self, db: AsyncSession, *, channel: str, payload: str) -> None:
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise RuntimeError("simulated notify failure")
        self.sent.append((channel, payload))


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
    async with async_session_test() as session:
        assert await fetch_unsent(session) == []


@pytest.mark.asyncio
async def test_drain_once_notifies_and_marks_sent():
    ids = await _stage_outbox(3)
    notifier = FakeNotifier()
    async with async_session_test() as session:
        n = await _drain_once(session, notifier, batch_size=10)

    assert n == 3
    assert len(notifier.sent) == 3

    channels = {channel for channel, _ in notifier.sent}
    assert channels == {"grade_events"}

    # Envelope = {"event_id": <id>} — workers fetch the full payload from
    # the outbox row, so only the id rides over NOTIFY.
    sent_ids = [json.loads(payload)["event_id"] for _, payload in notifier.sent]
    assert sent_ids == ids

    async with async_session_test() as session:
        assert await fetch_unsent(session) == []


@pytest.mark.asyncio
async def test_drain_once_empty_outbox_returns_zero():
    notifier = FakeNotifier()
    async with async_session_test() as session:
        n = await _drain_once(session, notifier)
    assert n == 0
    assert notifier.sent == []


@pytest.mark.asyncio
async def test_drain_once_rolls_back_on_notify_failure():
    """If notify raises mid-batch, the whole transaction rolls back so the
    rows stay unsent and SKIP LOCKED can release them for retry."""
    await _stage_outbox(5)
    notifier = FakeNotifier()

    call_count = 0

    async def flaky_notify(db, *, channel, payload):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            raise RuntimeError("notify hiccup")
        notifier.sent.append((channel, payload))

    notifier.notify = flaky_notify  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="notify hiccup"):
        async with async_session_test() as session:
            await _drain_once(session, notifier, batch_size=10)

    # Rollback semantics: no rows should be marked sent because the
    # transaction never committed.
    async with async_session_test() as session:
        unsent = await fetch_unsent(session)
    assert len(unsent) == 5


@pytest.mark.asyncio
async def test_run_loop_catches_up_after_simulated_outage():
    """Stage rows, run the loop briefly with a notifier that fails the first
    3 attempts, and verify all rows eventually get relayed."""
    await _stage_outbox(5)

    # Run a transient-failing notifier: fail the first batch entirely, then
    # succeed on retries. Because failures roll back, the first 3 retries
    # (each is a full batch attempt) all fail before the 4th succeeds.
    class TransientFailNotifier:
        def __init__(self):
            self.attempts = 0
            self.sent: list[tuple[str, str]] = []

        async def notify(self, db, *, channel, payload):
            self.attempts += 1
            if self.attempts <= 3:
                raise RuntimeError("transient")
            self.sent.append((channel, payload))

    notifier = TransientFailNotifier()
    stop = asyncio.Event()

    async def stopper():
        await asyncio.sleep(1.5)
        stop.set()

    asyncio.create_task(stopper())

    await run(
        session_factory=async_session_test,
        notifier=notifier,
        poll_interval_idle=0.05,
        backoff_initial=0.05,
        backoff_max=0.1,
        stop_event=stop,
    )

    async with async_session_test() as session:
        unsent = await fetch_unsent(session)
    assert unsent == [], f"publisher did not drain backlog (got {len(unsent)} unsent)"
    assert len(notifier.sent) == 5
