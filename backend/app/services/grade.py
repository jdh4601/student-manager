import uuid
from decimal import Decimal
from typing import List

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import AppException
from app.models.grade import Grade
from app.utils.grade_calculator import calculate_grade


async def create_grade(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    subject_id: uuid.UUID,
    semester_id: uuid.UUID,
    score: Decimal,
    created_by: uuid.UUID,
) -> Grade:
    grade_rank = calculate_grade(float(score)) if score is not None else None
    grade = Grade(
        student_id=student_id,
        subject_id=subject_id,
        semester_id=semester_id,
        score=score,
        grade_rank=grade_rank,
        created_by=created_by,
    )
    db.add(grade)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppException(409, "Duplicate grade", "GRADE_DUPLICATE")
    await db.refresh(grade)
    return grade


async def update_grade(
    db: AsyncSession,
    *,
    grade_id: uuid.UUID,
    score: Decimal,
) -> Grade:
    result = await db.execute(select(Grade).where(Grade.id == grade_id))
    grade = result.scalar_one_or_none()
    if grade is None:
        raise AppException(404, "Grade not found", "GRADE_NOT_FOUND")
    grade.score = score
    grade.grade_rank = calculate_grade(float(score))
    await db.commit()
    await db.refresh(grade)
    return grade


async def list_grades(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    semester_id: uuid.UUID | None = None,
) -> List[Grade]:
    stmt = select(Grade).where(Grade.student_id == student_id)
    if semester_id is not None:
        stmt = stmt.where(Grade.semester_id == semester_id)
    result = await db.execute(stmt)
    return result.scalars().all()

