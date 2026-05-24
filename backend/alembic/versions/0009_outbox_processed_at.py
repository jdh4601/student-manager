"""Add public.outbox.processed_at + retry/error columns for LISTEN/NOTIFY CDC

Revision ID: 0009_outbox_processed_at
Revises: 0008_fact_counseling_and_dlq
Create Date: 2026-05-23

Per ADR-003. Kafka removed; analytics-worker now consumes via Postgres
LISTEN/NOTIFY + `SELECT FOR UPDATE SKIP LOCKED`. The outbox table grows a
second state machine bit (`processed_at`) so workers can independently mark
"consumed" without losing the publisher's "relayed" mark (`sent_at`).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_outbox_processed_at"
down_revision = "0008_fact_counseling_and_dlq"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return

    op.add_column(
        "outbox",
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="public",
    )
    op.add_column(
        "outbox",
        sa.Column(
            "retry_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        schema="public",
    )
    op.add_column(
        "outbox",
        sa.Column("last_error", sa.Text, nullable=True),
        schema="public",
    )

    # Partial index for worker catch-up: rows that publisher relayed but
    # worker hasn't consumed yet. Kept cheap by excluding terminal rows.
    op.execute(
        "CREATE INDEX outbox_unprocessed_idx "
        "ON public.outbox (event_id) "
        "WHERE sent_at IS NOT NULL AND processed_at IS NULL"
    )

    # Dead-letter now keyed by outbox event_id (Kafka partition/offset_
    # columns kept nullable for migration history compatibility).
    op.add_column(
        "dead_letter_event",
        sa.Column("outbox_event_id", sa.BigInteger, nullable=True),
        schema="analytics",
    )


def downgrade() -> None:
    if not _is_postgres():
        return

    op.drop_column("dead_letter_event", "outbox_event_id", schema="analytics")
    op.execute("DROP INDEX IF EXISTS outbox_unprocessed_idx")
    op.drop_column("outbox", "last_error", schema="public")
    op.drop_column("outbox", "retry_count", schema="public")
    op.drop_column("outbox", "processed_at", schema="public")
