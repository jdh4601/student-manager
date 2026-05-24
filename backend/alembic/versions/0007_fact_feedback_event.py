"""Add analytics.fact_feedback_event table

Revision ID: 0007_fact_feedback_event
Revises: 0006_fact_attendance_semester
Create Date: 2026-05-17

SMS-79. Feedback events get their own fact table — same pattern as grade
and attendance — so idempotency rides on PK (event_id) + ON CONFLICT
DO NOTHING. agg_student_overall.feedback_count is recomputed from this
fact table (DISTINCT ON feedback_id, filter op != 'DELETE').

Design Spec §9.1 did not originally include a fact_feedback_event table;
this issue extends the schema to apply the same idempotency contract used
by other domains. To be reflected back into the spec.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision = "0007_fact_feedback_event"
down_revision = "0006_fact_attendance_semester"
branch_labels = None
depends_on = None


SCHEMA = "analytics"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return

    op.create_table(
        "fact_feedback_event",
        sa.Column("event_id", sa.BigInteger, sa.Identity(always=False), primary_key=True),
        sa.Column("feedback_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("semester_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(15)),
        sa.Column("op", sa.String(10), nullable=False),
        sa.Column("occurred_at", sa.TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fact_feedback_event_student_semester",
        "fact_feedback_event",
        ["student_id", "semester_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fact_feedback_event_feedback",
        "fact_feedback_event",
        ["feedback_id", sa.text("occurred_at DESC")],
        schema=SCHEMA,
    )


def downgrade() -> None:
    if not _is_postgres():
        return
    op.drop_index(
        "ix_fact_feedback_event_feedback", table_name="fact_feedback_event", schema=SCHEMA
    )
    op.drop_index(
        "ix_fact_feedback_event_student_semester",
        table_name="fact_feedback_event",
        schema=SCHEMA,
    )
    op.drop_table("fact_feedback_event", schema=SCHEMA)
