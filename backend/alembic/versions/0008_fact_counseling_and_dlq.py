"""Add fact_counseling_event + dead_letter_event tables

Revision ID: 0008_fact_counseling_and_dlq
Revises: 0007_fact_feedback_event
Create Date: 2026-05-17

SMS-80. Counseling events get their own fact table (audit / future BI use)
and the analytics layer gains a dead-letter table so poison messages
don't wedge the consumer.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision = "0008_fact_counseling_and_dlq"
down_revision = "0007_fact_feedback_event"
branch_labels = None
depends_on = None


SCHEMA = "analytics"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return

    op.create_table(
        "fact_counseling_event",
        sa.Column("event_id", sa.BigInteger, sa.Identity(always=False), primary_key=True),
        sa.Column("counseling_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("teacher_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date),
        sa.Column("op", sa.String(10), nullable=False),
        sa.Column("occurred_at", sa.TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fact_counseling_event_student",
        "fact_counseling_event",
        ["student_id", sa.text("occurred_at DESC")],
        schema=SCHEMA,
    )

    op.create_table(
        "dead_letter_event",
        sa.Column("id", sa.BigInteger, sa.Identity(always=False), primary_key=True),
        sa.Column("topic", sa.String(50), nullable=False),
        sa.Column("partition", sa.Integer),
        sa.Column("offset_", sa.BigInteger),
        sa.Column("raw_value", sa.LargeBinary),
        sa.Column("error", sa.Text, nullable=False),
        sa.Column("occurred_at", sa.TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )


def downgrade() -> None:
    if not _is_postgres():
        return
    op.drop_table("dead_letter_event", schema=SCHEMA)
    op.drop_index(
        "ix_fact_counseling_event_student",
        table_name="fact_counseling_event",
        schema=SCHEMA,
    )
    op.drop_table("fact_counseling_event", schema=SCHEMA)
