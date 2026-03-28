import io
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import require_role
from app.dependencies.db import get_db
from app.models.user import User
from app.models.subject import Subject
from app.services.import_ import (
    generate_grade_template,
    generate_student_template,
    import_grades_csv,
    import_grades_xlsx,
    import_students_csv,
    import_students_xlsx,
)

router = APIRouter(prefix="/import", tags=["import"]) 


@router.post("/students")
async def import_students(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    content = await file.read()
    result = await import_students_csv(
        db, teacher_id=current_user.id, school_id=current_user.school_id, content=content
    )
    return {"created": result.created, "skipped": result.skipped, "errors": result.errors}


@router.post("/grades")
async def import_grades(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    content = await file.read()
    result = await import_grades_csv(db, teacher_id=current_user.id, content=content)
    return {"created": result.created, "skipped": result.skipped, "errors": result.errors}


@router.post("/students/xlsx")
async def import_students_xlsx_endpoint(
    class_id: str = Query(..., description="등록할 반 ID"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    content = await file.read()
    result = await import_students_xlsx(
        db,
        teacher_id=current_user.id,
        school_id=current_user.school_id,
        class_id=uuid.UUID(class_id),
        content=content,
    )
    return {"created": result.created, "skipped": result.skipped, "errors": result.errors}


@router.post("/grades/xlsx")
async def import_grades_xlsx_endpoint(
    class_id: str = Query(..., description="반 ID"),
    semester_id: str = Query(..., description="학기 ID"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    content = await file.read()
    result = await import_grades_xlsx(
        db,
        teacher_id=current_user.id,
        class_id=uuid.UUID(class_id),
        semester_id=uuid.UUID(semester_id),
        content=content,
    )
    return {"created": result.created, "skipped": result.skipped, "errors": result.errors}


@router.get("/students/template")
async def download_student_template(
    current_user: User = Depends(require_role("teacher")),
):
    content = generate_student_template()
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=student_template.xlsx"},
    )


@router.get("/grades/template")
async def download_grade_template(
    class_id: str = Query(..., description="반 ID (과목 목록 조회용)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    # Determine subject names for class
    from sqlalchemy import select

    result = await db.execute(select(Subject).where(Subject.class_id == uuid.UUID(class_id)))
    subject_names = [s.name for s in result.scalars().all()]
    content = generate_grade_template(subject_names)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=grade_template.xlsx"},
    )
