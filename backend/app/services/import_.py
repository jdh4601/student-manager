import csv
import io
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.main import AppException
from app.services.grade import create_grade
from app.services.user import create_student_account


@dataclass
class ImportResult:
    created: int
    skipped: int
    errors: list[dict[str, Any]]


async def import_students_csv(
    db: AsyncSession,
    *,
    teacher_id: uuid.UUID,
    school_id: uuid.UUID,
    content: bytes,
) -> ImportResult:
    created = 0
    skipped = 0
    errors: list[dict[str, Any]] = []
    f = io.StringIO(content.decode("utf-8"))
    reader = csv.DictReader(f)
    required = {"email", "name", "class_id", "student_number"}
    if not required.issubset(set(reader.fieldnames or [])):
        missing = list(required - set(reader.fieldnames or []))
        errors.append({"row": 0, "error": f"Missing columns: {', '.join(missing)}"})
        return ImportResult(created, skipped, errors)

    from app.schemas.user import StudentCreate

    for idx, row in enumerate(reader, start=2):
        try:
            data = StudentCreate(
                email=row["email"],
                name=row["name"],
                class_id=row["class_id"],
                student_number=int(row["student_number"]),
                birth_date=row.get("birth_date") or None,
            )
            try:
                await create_student_account(db, school_id=school_id, teacher_id=teacher_id, data=data)
                created += 1
            except AppException as e:
                if e.code == "USER_DUPLICATE_EMAIL":
                    skipped += 1
                else:
                    errors.append({"row": idx, "error": f"{e.code}:{e.detail}"})
        except Exception as e:  # validation error
            errors.append({"row": idx, "error": str(e)})

    return ImportResult(created, skipped, errors)


async def import_grades_csv(
    db: AsyncSession,
    *,
    teacher_id: uuid.UUID,
    content: bytes,
) -> ImportResult:
    created = 0
    skipped = 0
    errors: list[dict[str, Any]] = []
    f = io.StringIO(content.decode("utf-8"))
    reader = csv.DictReader(f)
    required = {"student_id", "subject_id", "semester_id", "score"}
    if not required.issubset(set(reader.fieldnames or [])):
        missing = list(required - set(reader.fieldnames or []))
        errors.append({"row": 0, "error": f"Missing columns: {', '.join(missing)}"})
        return ImportResult(created, skipped, errors)

    for idx, row in enumerate(reader, start=2):
        try:
            try:
                await create_grade(
                    db,
                    student_id=uuid.UUID(row["student_id"]),
                    subject_id=uuid.UUID(row["subject_id"]),
                    semester_id=uuid.UUID(row["semester_id"]),
                    score=Decimal(row["score"]),
                    created_by=teacher_id,
                    teacher_id=teacher_id,
                )
                created += 1
            except AppException as e:
                errors.append({"row": idx, "error": f"{e.code}:{e.detail}"})
        except Exception as e:
            errors.append({"row": idx, "error": str(e)})

    return ImportResult(created, skipped, errors)

