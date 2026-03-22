import uuid
from typing import List, Tuple

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import AppException
from app.models.class_ import Class
from app.models.parent_student import ParentStudent
from app.models.student import Student
from app.models.user import User
from app.schemas.user import ParentCreate, StudentCreate
from app.utils.security import hash_password


async def create_student_account(
    db: AsyncSession,
    *,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
    data: StudentCreate,
) -> Tuple[User, Student]:
    # Ensure class belongs to the same school
    result = await db.execute(select(Class).where(Class.id == uuid.UUID(data.class_id)))
    cls = result.scalar_one_or_none()
    if cls is None or cls.school_id != school_id:
        raise AppException(404, "Class not found", "CLASS_NOT_FOUND")

    user = User(
        school_id=school_id,
        email=str(data.email),
        hashed_password=hash_password("password123"),
        role="student",
        name=data.name,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppException(409, "Duplicate email", "USER_DUPLICATE_EMAIL")

    student = Student(
        user_id=user.id,
        class_id=cls.id,
        student_number=data.student_number,
        birth_date=data.birth_date,
    )
    db.add(student)
    await db.commit()
    await db.refresh(user)
    await db.refresh(student)
    return user, student


async def create_parent_account(
    db: AsyncSession,
    *,
    school_id: uuid.UUID,
    data: ParentCreate,
) -> Tuple[User, ParentStudent]:
    # validate student exists and same school
    result = await db.execute(select(Student, User).join(User, Student.user_id == User.id).where(Student.id == uuid.UUID(data.student_id)))
    row = result.first()
    if row is None:
        raise AppException(404, "Student not found", "STUDENT_NOT_FOUND")
    student, student_user = row
    if student_user.school_id != school_id:
        raise AppException(404, "Student not found", "STUDENT_NOT_FOUND")

    parent = User(
        school_id=school_id,
        email=str(data.email),
        hashed_password=hash_password("password123"),
        role="parent",
        name=data.name,
    )
    db.add(parent)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppException(409, "Duplicate email", "USER_DUPLICATE_EMAIL")

    link = ParentStudent(parent_id=parent.id, student_id=student.id)
    db.add(link)
    await db.commit()
    await db.refresh(parent)
    await db.refresh(link)
    return parent, link


async def list_students(
    db: AsyncSession,
    *,
    teacher_id: uuid.UUID,
    class_id: uuid.UUID | None,
) -> List[tuple[Student, User]]:
    # Only list students of teacher's classes
    class_query = select(Class.id).where(Class.teacher_id == teacher_id)
    if class_id is not None:
        class_query = class_query.where(Class.id == class_id)

    result = await db.execute(
        select(Student, User)
        .join(User, Student.user_id == User.id)
        .where(Student.class_id.in_(class_query))
        .order_by(Student.student_number)
    )
    return result.all()


async def deactivate_student(db: AsyncSession, *, student_id: uuid.UUID, teacher_id: uuid.UUID):
    result = await db.execute(select(Student, User, Class).join(User, Student.user_id == User.id).join(Class, Student.class_id == Class.id).where(Student.id == student_id))
    row = result.first()
    if row is None:
        raise AppException(404, "Student not found", "STUDENT_NOT_FOUND")
    student, user, cls = row
    if cls.teacher_id != teacher_id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")
    user.is_active = False
    await db.commit()

