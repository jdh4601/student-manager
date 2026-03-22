import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_role
from app.dependencies.db import get_db
from app.models.user import User
from app.schemas.grade import GradeCreate, GradeResponse
from app.services.grade import create_grade, list_grades, update_grade

router = APIRouter(prefix="/grades", tags=["grades"]) 


@router.post("", response_model=GradeResponse, status_code=status.HTTP_201_CREATED)
async def create_grade_endpoint(
    body: GradeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    grade = await create_grade(
        db,
        student_id=uuid.UUID(body.student_id),
        subject_id=uuid.UUID(body.subject_id),
        semester_id=uuid.UUID(body.semester_id),
        score=Decimal(body.score),
        created_by=current_user.id,
    )
    return GradeResponse(
        id=str(grade.id),
        student_id=str(grade.student_id),
        subject_id=str(grade.subject_id),
        semester_id=str(grade.semester_id),
        score=grade.score,
        grade_rank=grade.grade_rank,
    )


@router.put("/{grade_id}", response_model=GradeResponse)
async def update_grade_endpoint(
    grade_id: str,
    body: GradeCreate,  # reuse for simplicity (score only relevant on update)
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("teacher")),
):
    grade = await update_grade(db, grade_id=uuid.UUID(grade_id), score=Decimal(body.score))
    return GradeResponse(
        id=str(grade.id),
        student_id=str(grade.student_id),
        subject_id=str(grade.subject_id),
        semester_id=str(grade.semester_id),
        score=grade.score,
        grade_rank=grade.grade_rank,
    )


@router.get("", response_model=list[GradeResponse])
async def list_grades_endpoint(
    student_id: str,
    semester_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("teacher")),
):
    sid = uuid.UUID(student_id)
    sem = uuid.UUID(semester_id) if semester_id else None
    rows = await list_grades(db, student_id=sid, semester_id=sem)
    return [
        GradeResponse(
            id=str(g.id),
            student_id=str(g.student_id),
            subject_id=str(g.subject_id),
            semester_id=str(g.semester_id),
            score=g.score,
            grade_rank=g.grade_rank,
        )
        for g in rows
    ]

