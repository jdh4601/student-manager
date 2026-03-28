"""
Initial schema for Student Manager

Reflects current SQLAlchemy models as of initial release.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # schools
    op.create_table(
        "schools",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("subscription_status", sa.String(length=20), nullable=False, server_default=sa.text("'trial'")),
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("school_id", pg.UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # classes
    op.create_table(
        "classes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("school_id", pg.UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("grade", sa.SmallInteger(), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("teacher_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    # semesters
    op.create_table(
        "semesters",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("term", sa.SmallInteger(), nullable=False),
        sa.UniqueConstraint("year", "term", name="uq_semester_year_term"),
    )

    # students
    op.create_table(
        "students",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("class_id", pg.UUID(as_uuid=True), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("student_number", sa.SmallInteger(), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
    )

    # subjects
    op.create_table(
        "subjects",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("class_id", pg.UUID(as_uuid=True), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
    )

    # grades
    op.create_table(
        "grades",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("student_id", pg.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("subject_id", pg.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("semester_id", pg.UUID(as_uuid=True), sa.ForeignKey("semesters.id"), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("grade_rank", sa.SmallInteger(), nullable=True),
        sa.Column("created_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)", name="ck_grade_score_range"),
        sa.UniqueConstraint("student_id", "subject_id", "semester_id"),
    )
    op.create_index("ix_grades_student_semester", "grades", ["student_id", "semester_id"])

    # attendances
    op.create_table(
        "attendances",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("student_id", pg.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=15), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.UniqueConstraint("student_id", "date"),
    )
    op.create_index("ix_attendances_student_date", "attendances", ["student_id", "date"])

    # special_notes
    op.create_table(
        "special_notes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("student_id", pg.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    # feedbacks
    op.create_table(
        "feedbacks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("student_id", pg.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("teacher_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(length=15), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_visible_to_student", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_visible_to_parent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_feedbacks_student_teacher", "feedbacks", ["student_id", "teacher_id"])

    # counselings
    op.create_table(
        "counselings",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("student_id", pg.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("teacher_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("next_plan", sa.Text(), nullable=True),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_counselings_student_id", "counselings", ["student_id"])
    op.create_index("ix_counselings_teacher_id", "counselings", ["teacher_id"])
    op.create_index("ix_counselings_teacher_shared", "counselings", ["teacher_id", "is_shared"])

    # notifications
    op.create_table(
        "notifications",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("recipient_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("related_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("related_type", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_notifications_recipient_read", "notifications", ["recipient_id", "is_read"])
    op.create_index("ix_notifications_recipient_created", "notifications", ["recipient_id", "created_at"])

    # notification_preferences
    op.create_table(
        "notification_preferences",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("grade_input", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("feedback_created", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("counseling_updated", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # parent_students
    op.create_table(
        "parent_students",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("parent_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("student_id", pg.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.UniqueConstraint("parent_id", "student_id", name="uq_parent_student"),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("parent_students")
    op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_recipient_created", table_name="notifications")
    op.drop_index("ix_notifications_recipient_read", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_counselings_teacher_shared", table_name="counselings")
    op.drop_index("ix_counselings_teacher_id", table_name="counselings")
    op.drop_index("ix_counselings_student_id", table_name="counselings")
    op.drop_table("counselings")
    op.drop_index("ix_feedbacks_student_teacher", table_name="feedbacks")
    op.drop_table("feedbacks")
    op.drop_table("special_notes")
    op.drop_index("ix_attendances_student_date", table_name="attendances")
    op.drop_table("attendances")
    op.drop_index("ix_grades_student_semester", table_name="grades")
    op.drop_table("grades")
    op.drop_table("subjects")
    op.drop_table("students")
    op.drop_table("semesters")
    op.drop_table("classes")
    op.drop_table("users")
    op.drop_table("schools")
