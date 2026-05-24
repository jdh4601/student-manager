"""Postgres LISTEN/NOTIFY round-trip smoke test (ADR-003 validation).

Opens two asyncpg connections to the same Postgres, LISTENs on a generated
channel from one and emits a NOTIFY from the other, then verifies the
listener received the payload. Mirrors the role of the old
``scripts/kafka_smoke.py`` for the new CDC pipeline.

Usage:
    python scripts/listen_notify_smoke.py [--dsn postgresql://sm:smpass@localhost:5432/student_manager]

Exit code 0 → round-trip OK, 1 → failure.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid


def _coerce_dsn(url: str) -> str:
    """asyncpg accepts plain ``postgresql://...`` but not the ``+asyncpg`` driver tag."""
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


async def _run(dsn: str) -> int:
    import asyncpg

    channel = f"sms_smoke_{uuid.uuid4().hex[:8]}"
    payload = {"event_id": uuid.uuid4().hex, "marker": "listen-notify-ok"}
    payload_str = json.dumps(payload)

    received: asyncio.Future[str] = asyncio.get_running_loop().create_future()

    def on_notify(conn, pid, ch, value):  # noqa: ARG001
        if not received.done():
            received.set_result(value)

    listener = await asyncpg.connect(dsn)
    notifier = await asyncpg.connect(dsn)
    try:
        await listener.add_listener(channel, on_notify)
        print(f"[1/3] LISTEN on channel={channel}", flush=True)

        await notifier.execute("SELECT pg_notify($1, $2)", channel, payload_str)
        print("[2/3] NOTIFY emitted", flush=True)

        try:
            got = await asyncio.wait_for(received, timeout=10)
        except asyncio.TimeoutError:
            print("FAIL: did not receive NOTIFY within 10s", file=sys.stderr)
            return 1
        print(f"[3/3] received: {got}", flush=True)

        if json.loads(got) != payload:
            print(
                f"FAIL: payload mismatch (sent={payload_str}, got={got})",
                file=sys.stderr,
            )
            return 1
    finally:
        try:
            await listener.remove_listener(channel, on_notify)
        finally:
            await listener.close()
            await notifier.close()

    print("PASS — Postgres LISTEN/NOTIFY round-trip OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql://sm:smpass@localhost:5432/student_manager",
    )
    parser.add_argument("--dsn", default=default_dsn)
    args = parser.parse_args()

    return asyncio.run(_run(_coerce_dsn(args.dsn)))


if __name__ == "__main__":
    sys.exit(main())
