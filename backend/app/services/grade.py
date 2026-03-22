import uuid
from decimal import Decimal
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import AppException
from app.models.grade import Grade
from app.models.student import Student
from app.models.class_ import Class
from app.models.subject import Subject
from app.utils.grade_calculator import calculate_grade


async def create_grade(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    subject_id: uuid.UUID,
    semester_id: uuid.UUID,
    score: Decimal,
    created_by: uuid.UUID,
    teacher_id: uuid.UUID,
) -> Grade:
    # Verify student belongs to a class owned by teacher
    result = await db.execute(
        select(Student, Class).join(Class, Student.class_id == Class.id).where(Student.id == student_id)
    )
    row = result.first()
    if row is None:
        raise AppException(404, "Student not found", "STUDENT_NOT_FOUND")
    student, cls = row
    if cls.teacher_id != teacher_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")

    # Verify subject exists and is for the same class
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    if subject is None:
        raise AppException(404, "Subject not found", "SUBJECT_NOT_FOUND")
    if subject.class_id != student.class_id:
        raise AppException(400, "Subject does not belong to student's class", "SUBJECT_CLASS_MISMATCH")
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
    teacher_id: uuid.UUID,
) -> Grade:
    # Verify grade exists and teacher owns the student's class
    result = await db.execute(
        select(Grade, Student, Class)
        .join(Student, Grade.student_id == Student.id)
        .join(Class, Student.class_id == Class.id)
        .where(Grade.id == grade_id)
    )
    row = result.first()
    if row is None:
        raise AppException(404, "Grade not found", "GRADE_NOT_FOUND")
    grade, student, cls = row
    if cls.teacher_id != teacher_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")
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
    teacher_id: uuid.UUID,
) -> List[Grade]:
    # Verify teacher owns the student's class
    result = await db.execute(
        select(Student, Class).join(Class, Student.class_id == Class.id).where(Student.id == student_id)
    )
    row = result.first()
    if row is None:
        raise AppException(404, "Student not found", "STUDENT_NOT_FOUND")
    student, cls = row
    if cls.teacher_id != teacher_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")

    stmt = select(Grade).where(Grade.student_id == student_id)
    if semester_id is not None:
        stmt = stmt.where(Grade.semester_id == semester_id)
    result = await db.execute(stmt)
    return result.scalars().all()
