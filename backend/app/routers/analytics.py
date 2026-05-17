"""Analytics read API (Design Spec §9.5, REQ-073).

Endpoints return the projections written by ``app/workers/analytics.py`` —
the router itself does no aggregation. RBAC mirrors the operational
grades router: a teacher can read analytics only for students in classes
they own.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.analytics import get_student_overview_repo
from app.dependencies.auth import require_role
from app.dependencies.db import get_db
from app.errors import AppException
from app.models.class_ import Class
from app.models.student import Student
from app.models.user import User
from app.schemas.analytics import (
    OverallSummary,
    StudentOverviewResponse,
    SubjectOverview,
)
from app.services.analytics_query import StudentOverviewRepo

router = APIRouter(prefix="/analytics", tags=["analytics"])


async def _assert_teacher_owns_student(
    db: AsyncSession, *, student_id: uuid.UUID, teacher: User
) -> None:
    result = await db.execute(
        select(Student, Class)
        .join(Class, Student.class_id == Class.id)
        .where(Student.id == student_id)
    )
    row = result.first()
    if row is None:
        raise AppException(404, "Student not found", "STUDENT_NOT_FOUND")
    _student, cls = row
    if cls.school_id != teacher.school_id or cls.teacher_id != teacher.id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")


@router.get("/students/{student_id}/overview", response_model=StudentOverviewResponse)
async def get_student_overview(
    student_id: str,
    semester_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
    repo: StudentOverviewRepo = Depends(get_student_overview_repo),
) -> StudentOverviewResponse:
    sid = uuid.UUID(student_id)
    sem = uuid.UUID(semester_id) if semester_id else None

    await _assert_teacher_owns_student(db, student_id=sid, teacher=current_user)

    overall = await repo.get_overall(student_id=sid, semester_id=sem)
    subjects = await repo.get_subjects(student_id=sid, semester_id=sem)

    return StudentOverviewResponse(
        overall=OverallSummary.model_validate(overall) if overall else None,
        subjects=[
            SubjectOverview(
                subject_id=str(s.subject_id),
                name=s.name,
                avg_score=s.avg_score,
                max_score=s.max_score,
                min_score=s.min_score,
                latest_rank=s.latest_rank,
                sample_count=s.sample_count,
            )
            for s in subjects
        ],
    )
