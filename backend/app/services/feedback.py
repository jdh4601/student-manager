import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppException
from app.models.class_ import Class
from app.models.feedback import Feedback
from app.models.outbox import Outbox
from app.models.student import Student
from app.services.semester import current_semester_id


FEEDBACK_EVENTS_TOPIC = "feedback_events"


def _feedback_outbox_row(
    fb: Feedback, *, semester_id: uuid.UUID | None, op: str
) -> Outbox:
    payload = {
        "feedback_id": str(fb.id),
        "student_id": str(fb.student_id),
        "semester_id": str(semester_id) if semester_id is not None else None,
        "category": fb.category,
        "op": op,
    }
    return Outbox(
        aggregate_type="feedback",
        aggregate_id=fb.id,
        topic=FEEDBACK_EVENTS_TOPIC,
        payload=payload,
    )


async def _ensure_teacher_owns_student(db: AsyncSession, *, student_id: uuid.UUID, teacher_id: uuid.UUID) -> Student:
    result = await db.execute(
        select(Student, Class).join(Class, Student.class_id == Class.id).where(Student.id == student_id)
    )
    row = result.first()
    if row is None:
        raise AppException(404, "Student not found", "STUDENT_NOT_FOUND")
    student, cls = row
    if cls.teacher_id != teacher_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")
    return student


async def create_feedback(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    teacher_id: uuid.UUID,
    category: str,
    content: str,
    is_visible_to_student: bool,
    is_visible_to_parent: bool,
) -> Feedback:
    await _ensure_teacher_owns_student(db, student_id=student_id, teacher_id=teacher_id)
    fb = Feedback(
        student_id=student_id,
        teacher_id=teacher_id,
        category=category,
        content=content,
        is_visible_to_student=is_visible_to_student,
        is_visible_to_parent=is_visible_to_parent,
    )
    db.add(fb)
    await db.flush()  # populate fb.id before staging outbox row
    semester_id = await current_semester_id(db)
    db.add(_feedback_outbox_row(fb, semester_id=semester_id, op="INSERT"))
    await db.commit()
    await db.refresh(fb)
    return fb


async def update_feedback(
    db: AsyncSession,
    *,
    feedback_id: uuid.UUID,
    teacher_id: uuid.UUID,
    content: str | None = None,
    is_visible_to_student: bool | None = None,
    is_visible_to_parent: bool | None = None,
) -> Feedback:
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    fb = result.scalar_one_or_none()
    if fb is None:
        raise AppException(404, "Feedback not found", "FEEDBACK_NOT_FOUND")
    if fb.teacher_id != teacher_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")
    if content is not None:
        fb.content = content
    if is_visible_to_student is not None:
        fb.is_visible_to_student = is_visible_to_student
    if is_visible_to_parent is not None:
        fb.is_visible_to_parent = is_visible_to_parent
    semester_id = await current_semester_id(db)
    db.add(_feedback_outbox_row(fb, semester_id=semester_id, op="UPDATE"))
    await db.commit()
    await db.refresh(fb)
    return fb


async def delete_feedback(db: AsyncSession, *, feedback_id: uuid.UUID, teacher_id: uuid.UUID) -> None:
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    fb = result.scalar_one_or_none()
    if fb is None:
        raise AppException(404, "Feedback not found", "FEEDBACK_NOT_FOUND")
    if fb.teacher_id != teacher_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")
    semester_id = await current_semester_id(db)
    # Stage outbox row BEFORE deleting so payload captures the final state.
    db.add(_feedback_outbox_row(fb, semester_id=semester_id, op="DELETE"))
    await db.delete(fb)
    await db.commit()


async def list_feedbacks_for_teacher(db: AsyncSession, *, teacher_id: uuid.UUID, student_id: uuid.UUID | None = None) -> List[Feedback]:
    stmt = select(Feedback).where(Feedback.teacher_id == teacher_id)
    if student_id is not None:
        stmt = stmt.where(Feedback.student_id == student_id)
    result = await db.execute(stmt.order_by(Feedback.created_at.desc()))
    return result.scalars().all()
