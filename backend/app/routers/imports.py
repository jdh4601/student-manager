from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import require_role
from app.dependencies.db import get_db
from app.models.user import User
from app.services.import_ import import_grades_csv, import_students_csv

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

