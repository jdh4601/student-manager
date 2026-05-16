import uuid
from datetime import date
from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppException
from app.models.class_ import Class
from app.models.counseling import Counseling
from app.models.outbox import Outbox
from app.models.student import Student
from app.models.user import User


COUNSELING_EVENTS_TOPIC = "counseling_events"


def _counseling_outbox_row(cs: Counseling, *, op: str) -> Outbox:
    payload = {
        "counseling_id": str(cs.id),
        "student_id": str(cs.student_id),
        "teacher_id": str(cs.teacher_id),
        "date": cs.date.isoformat(),
        "op": op,
    }
    return Outbox(
        aggregate_type="counseling",
        aggregate_id=cs.id,
        topic=COUNSELING_EVENTS_TOPIC,
        payload=payload,
    )


async def _student_with_class(db: AsyncSession, student_id: uuid.UUID):
    result = await db.execute(
        select(Student, Class).join(Class, Student.class_id == Class.id).where(Student.id == student_id)
    )
    return result.first()


async def create_counseling(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    teacher_id: uuid.UUID,
    date,
    content: str,
    next_plan: str | None,
    is_shared: bool,
) -> Counseling:
    row = await _student_with_class(db, student_id)
    if row is None:
        raise AppException(404, "Student not found", "STUDENT_NOT_FOUND")
    student, cls = row
    if cls.teacher_id != teacher_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")
    cs = Counseling(
        student_id=student_id,
        teacher_id=teacher_id,
        date=date,
        content=content,
        next_plan=next_plan,
        is_shared=is_shared,
    )
    db.add(cs)
    await db.flush()  # populate cs.id before staging outbox row
    db.add(_counseling_outbox_row(cs, op="INSERT"))
    await db.commit()
    await db.refresh(cs)
    return cs


async def update_counseling(
    db: AsyncSession,
    *,
    counseling_id: uuid.UUID,
    teacher_id: uuid.UUID,
    content: str | None = None,
    next_plan: str | None = None,
    is_shared: bool | None = None,
) -> Counseling:
    result = await db.execute(select(Counseling).where(Counseling.id == counseling_id))
    cs = result.scalar_one_or_none()
    if cs is None:
        raise AppException(404, "Counseling not found", "COUNSELING_NOT_FOUND")
    if cs.teacher_id != teacher_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")
    if content is not None:
        cs.content = content
    if next_plan is not None:
        cs.next_plan = next_plan
    if is_shared is not None:
        cs.is_shared = is_shared
    db.add(_counseling_outbox_row(cs, op="UPDATE"))
    await db.commit()
    await db.refresh(cs)
    return cs


async def list_counselings(
    db: AsyncSession,
    *,
    teacher_id: uuid.UUID,
    school_id: uuid.UUID,
    student_id: Optional[uuid.UUID] = None,
    student_name: Optional[str] = None,
    teacher_name: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    include_shared: bool = False,
) -> List[tuple[Counseling, str, str]]:
    student_user = aliased(User)
    teacher_user = aliased(User)

    stmt = (
        select(Counseling, student_user.name, teacher_user.name)
        .join(Student, Counseling.student_id == Student.id)
        .join(Class, Student.class_id == Class.id)
        .join(student_user, Student.user_id == student_user.id)
        .join(teacher_user, Counseling.teacher_id == teacher_user.id)
        .where(Class.school_id == school_id)
    )

    if student_id is not None:
        stmt = stmt.where(Counseling.student_id == student_id)

    if include_shared or student_id is not None:
        stmt = stmt.where(
            or_(
                Counseling.teacher_id == teacher_id,
                Counseling.is_shared.is_(True),
            )
        )
    else:
        stmt = stmt.where(Counseling.teacher_id == teacher_id)

    if student_name:
        stmt = stmt.where(student_user.name.ilike(f"%{student_name}%"))
    if teacher_name:
        stmt = stmt.where(teacher_user.name.ilike(f"%{teacher_name}%"))
    if start_date:
        stmt = stmt.where(Counseling.date >= start_date)
    if end_date:
        stmt = stmt.where(Counseling.date <= end_date)

    result = await db.execute(stmt.order_by(Counseling.date.desc(), Counseling.created_at.desc()))
    return list(result.all())


async def delete_counseling(
    db: AsyncSession,
    *,
    counseling_id: uuid.UUID,
    teacher_id: uuid.UUID,
) -> None:
    result = await db.execute(select(Counseling).where(Counseling.id == counseling_id))
    cs = result.scalar_one_or_none()
    if cs is None:
        raise AppException(404, "Counseling not found", "COUNSELING_NOT_FOUND")
    if cs.teacher_id != teacher_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")
    await db.delete(cs)
    await db.commit()
