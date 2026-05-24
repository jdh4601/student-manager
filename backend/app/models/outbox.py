"""Outbox table for transactional outbox CDC pattern (ADR-003, Design Spec §9.1).

Operational routers (grade/attendance/feedback/counseling) INSERT into this
table within the same transaction as the domain write. The outbox-publisher
worker polls `WHERE sent_at IS NULL` (FOR UPDATE SKIP LOCKED) and emits a
Postgres NOTIFY on the matching channel. analytics-worker LISTENs on the
channels, then locks the outbox row via `WHERE processed_at IS NULL
FOR UPDATE SKIP LOCKED` so scale=N workers cooperate without duplicate work.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Outbox(Base):
    """Cross-platform mapping. Production schema (alembic 0005/0009) uses
    BIGINT IDENTITY + JSONB + partial indexes — SQLAlchemy reads/writes it
    through the simpler portable types below.

    State machine:
      - `sent_at IS NULL` → publisher hasn't relayed yet
      - `sent_at IS NOT NULL AND processed_at IS NULL` → worker hasn't consumed
      - `processed_at IS NOT NULL` → terminal
    """

    __tablename__ = "outbox"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    topic: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
