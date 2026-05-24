"""Add semester_id column to analytics.fact_attendance_event

Revision ID: 0006_fact_attendance_semester
Revises: 0005_outbox_table
Create Date: 2026-05-17

SMS-78. attendance events need a semester_id projection so the
agg_student_overall.attendance_present_rate UPSERT can scope the rate to
a single (student, semester). Resolved at outbox INSERT time (operational
side), stored on the fact row by the analytics consumer.

Nullable to avoid blocking on a backfill — backfill is a separate concern
once historical attendance is reprojected.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision = "0006_fact_attendance_semester"
down_revision = "0005_outbox_table"
branch_labels = None
depends_on = None


SCHEMA = "analytics"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return
    op.add_column(
        "fact_attendance_event",
        sa.Column("semester_id", pg.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fact_attendance_event_student_semester",
        "fact_attendance_event",
        ["student_id", "semester_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    if not _is_postgres():
        return
    op.drop_index(
        "ix_fact_attendance_event_student_semester",
        table_name="fact_attendance_event",
        schema=SCHEMA,
    )
    op.drop_column("fact_attendance_event", "semester_id", schema=SCHEMA)
