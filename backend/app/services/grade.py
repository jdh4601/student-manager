import uuid
from decimal import Decimal
from typing import List

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppException
from app.models.grade import Grade
from app.models.outbox import Outbox
from app.models.student import Student
from app.models.class_ import Class
from app.models.subject import Subject
from app.utils.grade_calculator import calculate_grade


GRADE_EVENTS_TOPIC = "grade_events"


def _grade_outbox_row(grade: Grade, *, op: str) -> Outbox:
    """Build an outbox row for a grade write — staged in the same session as the grade."""
    payload = {
        "grade_id": str(grade.id),
        "student_id": str(grade.student_id),
        "subject_id": str(grade.subject_id),
        "semester_id": str(grade.semester_id),
        "score": float(grade.score) if grade.score is not None else None,
        "grade_rank": grade.grade_rank,
        "op": op,
    }
    return Outbox(
        aggregate_type="grade",
        aggregate_id=grade.id,
        topic=GRADE_EVENTS_TOPIC,
        payload=payload,
    )


def _raise_forbidden() -> None:
    raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")


async def _get_owned_student(db: AsyncSession, *, student_id: uuid.UUID, teacher_id: uuid.UUID) -> Student:
    result = await db.execute(
        select(Student, Class).join(Class, Student.class_id == Class.id).where(Student.id == student_id)
    )
    row = result.first()
    if row is None:
        raise AppException(404, "Student not found", "STUDENT_NOT_FOUND")

    student, cls = row
    if cls.teacher_id != teacher_id:
        _raise_forbidden()
    return student


async def _get_subject_for_student_class(
    db: AsyncSession,
    *,
    subject_id: uuid.UUID,
    student_class_id: uuid.UUID,
) -> Subject:
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    if subject is None:
        raise AppException(404, "Subject not found", "SUBJECT_NOT_FOUND")
    if subject.class_id != student_class_id:
        raise AppException(400, "Subject does not belong to student's class", "SUBJECT_CLASS_MISMATCH")
    return subject


async def _get_owned_grade(db: AsyncSession, *, grade_id: uuid.UUID, teacher_id: uuid.UUID) -> Grade:
    result = await db.execute(
        select(Grade, Class)
        .join(Student, Grade.student_id == Student.id)
        .join(Class, Student.class_id == Class.id)
        .where(Grade.id == grade_id)
    )
    row = result.first()
    if row is None:
        raise AppException(404, "Grade not found", "GRADE_NOT_FOUND")

    grade, cls = row
    if cls.teacher_id != teacher_id:
        _raise_forbidden()
    return grade


def _student_grades_stmt(student_id: uuid.UUID, semester_id: uuid.UUID | None):
    stmt = select(Grade).where(Grade.student_id == student_id)
    if semester_id is not None:
        stmt = stmt.where(Grade.semester_id == semester_id)
    return stmt


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
    student = await _get_owned_student(db, student_id=student_id, teacher_id=teacher_id)
    await _get_subject_for_student_class(db, subject_id=subject_id, student_class_id=student.class_id)
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
        await db.flush()  # populate grade.id before staging outbox row
        db.add(_grade_outbox_row(grade, op="INSERT"))
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
    grade = await _get_owned_grade(db, grade_id=grade_id, teacher_id=teacher_id)
    grade.score = score
    grade.grade_rank = calculate_grade(float(score))
    db.add(_grade_outbox_row(grade, op="UPDATE"))
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
    await _get_owned_student(db, student_id=student_id, teacher_id=teacher_id)

    stmt = _student_grades_stmt(student_id, semester_id)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_grade_summary(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    semester_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID,
):
    await _get_owned_student(db, student_id=student_id, teacher_id=teacher_id)

    # Aggregate (ignore NULL scores)
    agg_stmt = select(
        func.sum(Grade.score),
        func.avg(Grade.score),
        func.count(Grade.id),
    ).where(Grade.student_id == student_id)
    if semester_id is not None:
        agg_stmt = agg_stmt.where(Grade.semester_id == semester_id)
    agg_stmt = agg_stmt.where(Grade.score.isnot(None))
    agg_result = await db.execute(agg_stmt)
    total, average, count = agg_result.one_or_none() or (None, None, 0)

    # List grades for the same scope
    stmt = _student_grades_stmt(student_id, semester_id)
    rows_result = await db.execute(stmt)
    grades = rows_result.scalars().all()

    return {
        "total": total,
        "average": average,
        "count": int(count or 0),
        "grades": grades,
    }
