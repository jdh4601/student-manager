import pytest
from sqlalchemy import inspect


@pytest.mark.asyncio
async def test_all_tables_created(setup_db):
    """All 14 entity tables should be created from models."""
    # Import to trigger model registration
    from app.models import (  # noqa: F401
        Attendance,
        Class,
        Counseling,
        Feedback,
        Grade,
        Notification,
        NotificationPreference,
        ParentStudent,
        School,
        Semester,
        SpecialNote,
        Student,
        Subject,
        User,
    )
    from tests.conftest import engine_test

    async with engine_test.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )

    expected = {
        "schools",
        "users",
        "classes",
        "students",
        "parent_students",
        "subjects",
        "semesters",
        "grades",
        "attendances",
        "special_notes",
        "feedbacks",
        "counselings",
        "notifications",
        "notification_preferences",
    }
    assert expected.issubset(set(table_names))

