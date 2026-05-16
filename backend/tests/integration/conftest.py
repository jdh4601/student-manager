"""Session-scoped Docker fixtures for end-to-end pipeline tests (SMS-54).

Spins up a real Kafka (KRaft) + Postgres via testcontainers, runs alembic
upgrade head against the Postgres container so the operational + analytics
schemas are both present.

Cost: ~25-40s startup (image pull on first run). Tests are marked
`@pytest.mark.integration` so they're excluded from `pytest` by default —
use `pytest -m integration` (or `npm run qa:e2e`) to run them.
"""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.kafka import KafkaContainer
from testcontainers.postgres import PostgresContainer

# Allow the suite to be collected even if Docker is absent — the actual
# container .start() will fail with a clear error during fixture setup.


def _async_pg_url(sync_url: str) -> str:
    """testcontainers gives psycopg2-style URLs; we need asyncpg for app code."""
    if sync_url.startswith("postgresql+psycopg2://"):
        return sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def kafka_container() -> Iterator[KafkaContainer]:
    # KRaft mode mirrors the production docker-compose topology.
    container = KafkaContainer("confluentinc/cp-kafka:7.6.1").with_kraft()
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def kafka_bootstrap(kafka_container: KafkaContainer) -> str:
    return kafka_container.get_bootstrap_server()


@pytest.fixture(scope="session")
def pg_async_url(postgres_container: PostgresContainer) -> str:
    return _async_pg_url(postgres_container.get_connection_url())


@pytest.fixture(scope="session")
def pg_sync_url(postgres_container: PostgresContainer) -> str:
    """psycopg2-compatible URL — used by alembic which runs sync."""
    url = postgres_container.get_connection_url()
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return url


@pytest.fixture(scope="session", autouse=False)
def _migrate_schema(pg_sync_url: str) -> None:
    """Run `alembic upgrade head` once per session against the Postgres container."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", pg_sync_url)
    command.upgrade(cfg, "head")


@pytest.fixture
async def db_engine(pg_async_url: str, _migrate_schema: None) -> AsyncIterator:
    engine = create_async_engine(pg_async_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def session_factory(db_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def clean_pipeline_tables(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Truncate outbox + analytics tables between tests.

    Note: we deliberately do NOT ``RESTART IDENTITY`` because event_ids leak
    onto the Kafka topic (which persists across tests within the session).
    Resetting the sequence would let test N reuse event_ids that test N-1
    already published, and the consumer's ``ON CONFLICT (event_id) DO NOTHING``
    dedup would silently drop test N's new events.
    """
    from sqlalchemy import text

    async with session_factory() as db:
        await db.execute(text("TRUNCATE TABLE public.outbox CASCADE"))
        await db.execute(text("TRUNCATE TABLE analytics.fact_grade_event CASCADE"))
        await db.execute(text("TRUNCATE TABLE analytics.agg_student_subject"))
        await db.execute(text("TRUNCATE TABLE analytics.agg_student_overall"))
        await db.commit()


@pytest.fixture
def unique_uuids() -> dict[str, uuid.UUID]:
    """Pre-allocated UUIDs so a test can stage outbox rows without seeding the
    full operational schema (student/subject/etc.) — analytics tables don't
    enforce FKs to operational, so synthetic UUIDs work for fact + agg checks."""
    return {
        "grade": uuid.uuid4(),
        "student": uuid.uuid4(),
        "subject": uuid.uuid4(),
        "semester": uuid.uuid4(),
    }


@pytest.fixture
async def stop_event() -> asyncio.Event:
    return asyncio.Event()
