import uuid
from datetime import date
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppException
from app.models.attendance import Attendance
from app.models.class_ import Class
from app.models.outbox import Outbox
from app.models.special_note import SpecialNote
from app.models.student import Student
from app.models.user import User
from app.models.feedback import Feedback
from app.models.counseling import Counseling
from app.models.parent_student import ParentStudent
from app.models.grade import Grade
from app.schemas.user import StudentCreate
from app.services.semester import current_semester_id
from app.services.user import create_student_account


ATTENDANCE_EVENTS_TOPIC = "attendance_events"


def _attendance_outbox_row(att: Attendance, *, semester_id: uuid.UUID | None, op: str) -> Outbox:
    payload = {
        "attendance_id": str(att.id),
        "student_id": str(att.student_id),
        "semester_id": str(semester_id) if semester_id is not None else None,
        "date": att.date.isoformat(),
        "status": att.status,
        "op": op,
    }
    return Outbox(
        aggregate_type="attendance",
        aggregate_id=att.id,
        topic=ATTENDANCE_EVENTS_TOPIC,
        payload=payload,
    )


async def _teacher_owns_student(db: AsyncSession, *, student_id: uuid.UUID, teacher_id: uuid.UUID) -> tuple[Student, User, Class]:
    result = await db.execute(
        select(Student, User, Class)
        .join(User, Student.user_id == User.id)
        .join(Class, Student.class_id == Class.id)
        .where(Student.id == student_id)
    )
    row = result.first()
    if row is None:
        raise AppException(404, "Student not found", "STUDENT_NOT_FOUND")
    student, user, cls = row
    if cls.teacher_id != teacher_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")
    return student, user, cls


async def get_student_detail(db: AsyncSession, *, student_id: uuid.UUID, teacher_id: uuid.UUID) -> tuple[Student, User]:
    student, user, _ = await _teacher_owns_student(db, student_id=student_id, teacher_id=teacher_id)
    return student, user


async def update_student(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    teacher_id: uuid.UUID,
    name: str | None,
    student_number: int | None,
    birth_date: date | None,
    gender: str | None = None,
    phone: str | None = None,
    address: str | None = None,
) -> tuple[Student, User]:
    student, user, _ = await _teacher_owns_student(db, student_id=student_id, teacher_id=teacher_id)
    if name is not None:
        user.name = name
    if student_number is not None:
        student.student_number = student_number
    if birth_date is not None:
        student.birth_date = birth_date
    if gender is not None:
        student.gender = gender
    if phone is not None:
        student.phone = phone
    if address is not None:
        student.address = address
    await db.commit()
    await db.refresh(student)
    await db.refresh(user)
    return student, user


async def create_attendance(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    teacher_id: uuid.UUID,
    date_: date,
    status: str,
    note: str | None,
) -> Attendance:
    await _teacher_owns_student(db, student_id=student_id, teacher_id=teacher_id)
    semester_id = await current_semester_id(db)
    att = Attendance(student_id=student_id, date=date_, status=status, note=note)
    db.add(att)
    try:
        await db.flush()  # populate att.id before staging outbox row
        db.add(_attendance_outbox_row(att, semester_id=semester_id, op="INSERT"))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppException(409, "Attendance already exists for date", "ATTENDANCE_DUPLICATE_DATE")
    await db.refresh(att)
    return att


async def list_attendance(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    teacher_id: uuid.UUID,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Attendance]:
    await _teacher_owns_student(db, student_id=student_id, teacher_id=teacher_id)
    stmt = select(Attendance).where(Attendance.student_id == student_id)
    if start_date is not None:
        stmt = stmt.where(Attendance.date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Attendance.date <= end_date)
    result = await db.execute(stmt.order_by(Attendance.date.asc()))
    return result.scalars().all()


async def update_attendance(
    db: AsyncSession,
    *,
    attendance_id: uuid.UUID,
    teacher_id: uuid.UUID,
    status: str | None = None,
    note: str | None = None,
) -> Attendance:
    result = await db.execute(select(Attendance, Student, Class).join(Student, Attendance.student_id == Student.id).join(Class, Student.class_id == Class.id).where(Attendance.id == attendance_id))
    row = result.first()
    if row is None:
        raise AppException(404, "Attendance not found", "ATTENDANCE_NOT_FOUND")
    att, _student, cls = row
    if cls.teacher_id != teacher_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")
    if status is not None:
        att.status = status
    if note is not None:
        att.note = note
    semester_id = await current_semester_id(db)
    db.add(_attendance_outbox_row(att, semester_id=semester_id, op="UPDATE"))
    await db.commit()
    await db.refresh(att)
    return att


async def create_special_note(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    teacher_id: uuid.UUID,
    content: str,
) -> SpecialNote:
    await _teacher_owns_student(db, student_id=student_id, teacher_id=teacher_id)
    note = SpecialNote(student_id=student_id, content=content, created_by=teacher_id)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


async def update_special_note(
    db: AsyncSession,
    *,
    note_id: uuid.UUID,
    teacher_id: uuid.UUID,
    content: str,
) -> SpecialNote:
    result = await db.execute(select(SpecialNote).where(SpecialNote.id == note_id))
    note = result.scalar_one_or_none()
    if note is None:
        raise AppException(404, "Special note not found", "SPECIAL_NOTE_NOT_FOUND")
    if note.created_by != teacher_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")
    note.content = content
    await db.commit()
    await db.refresh(note)
    return note


async def list_special_notes(db: AsyncSession, *, student_id: uuid.UUID, teacher_id: uuid.UUID) -> List[SpecialNote]:
    await _teacher_owns_student(db, student_id=student_id, teacher_id=teacher_id)
    result = await db.execute(select(SpecialNote).where(SpecialNote.student_id == student_id).order_by(SpecialNote.created_at.desc()))
    return result.scalars().all()


async def create_student(
    db: AsyncSession,
    *,
    class_id: uuid.UUID,
    teacher_id: uuid.UUID,
    school_id: uuid.UUID,
    email: str,
    name: str,
    student_number: int,
    birth_date: date | None = None,
    gender: str | None = None,
    phone: str | None = None,
    address: str | None = None,
) -> tuple[Student, User, str, str]:
    # Validate class ownership and school scope
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if cls is None:
        raise AppException(404, "Class not found", "CLASS_NOT_FOUND")
    if cls.teacher_id != teacher_id or cls.school_id != school_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")

    # Prevent duplicate student_number within the class
    exists = await db.execute(
        select(Student).where(Student.class_id == class_id, Student.student_number == student_number)
    )
    if exists.scalar_one_or_none() is not None:
        raise AppException(409, "해당 번호의 학생이 이미 존재합니다.", "STUDENT_DUPLICATE_NUMBER")

    user, student, invitation, invite_url = await create_student_account(
        db,
        school_id=school_id,
        teacher_id=teacher_id,
        data=StudentCreate(
            email=email,
            name=name,
            class_id=str(class_id),
            student_number=student_number,
            birth_date=birth_date,
        ),
    )
    student.gender = gender
    student.phone = phone
    student.address = address
    await db.commit()
    await db.refresh(student)
    await db.refresh(user)
    return student, user, invitation.expires_at.isoformat(), invite_url


async def delete_student(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    teacher_id: uuid.UUID,
) -> None:
    student, _user, cls = await _teacher_owns_student(db, student_id=student_id, teacher_id=teacher_id)

    # Delete dependent rows first (mirror class force-delete ordering for student scope)
    await db.execute(delete(Grade).where(Grade.student_id == student.id))
    await db.execute(delete(Attendance).where(Attendance.student_id == student.id))
    await db.execute(delete(SpecialNote).where(SpecialNote.student_id == student.id))
    await db.execute(delete(Feedback).where(Feedback.student_id == student.id))
    await db.execute(delete(Counseling).where(Counseling.student_id == student.id))
    await db.execute(delete(ParentStudent).where(ParentStudent.student_id == student.id))

    await db.delete(student)
    await db.commit()
