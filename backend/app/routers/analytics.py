"""Analytics read API (Design Spec §9.5, REQ-073).

Endpoints return the projections written by ``app/workers/analytics.py`` —
the router itself does no aggregation. RBAC mirrors the operational
grades router: a teacher can read analytics only for students in classes
they own.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.analytics import (
    get_class_distribution_repo,
    get_student_overview_repo,
    get_teacher_dashboard_repo,
)
from app.dependencies.auth import require_role
from app.dependencies.db import get_db
from app.errors import AppException
from app.models.class_ import Class
from app.models.counseling import Counseling
from app.models.feedback import Feedback
from app.models.student import Student
from app.models.user import User
from app.schemas.analytics import (
    ClassDistributionResponse,
    DistributionBucket,
    OverallSummary,
    StudentOverviewResponse,
    SubjectOverview,
    TeacherDashboardClass,
    TeacherDashboardResponse,
)
from app.services.analytics_query import (
    ClassDistributionRepo,
    StudentOverviewRepo,
    TeacherDashboardRepo,
    bucketize,
    median,
)
from app.services.semester import current_semester_id

RECENT_FEEDBACK_WINDOW_DAYS = 7

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


async def _assert_teacher_owns_class(
    db: AsyncSession, *, class_id: uuid.UUID, teacher: User
) -> None:
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if cls is None:
        raise AppException(404, "Class not found", "CLASS_NOT_FOUND")
    if cls.school_id != teacher.school_id or cls.teacher_id != teacher.id:
        raise AppException(403, "권한이 부족합니다.", "FORBIDDEN")


@router.get(
    "/classes/{class_id}/distribution",
    response_model=ClassDistributionResponse,
)
async def get_class_distribution(
    class_id: str,
    subject_id: str = Query(...),
    semester_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
    repo: ClassDistributionRepo = Depends(get_class_distribution_repo),
) -> ClassDistributionResponse:
    cid = uuid.UUID(class_id)
    sub = uuid.UUID(subject_id)
    sem = uuid.UUID(semester_id) if semester_id else None

    await _assert_teacher_owns_class(db, class_id=cid, teacher=current_user)

    scores = await repo.get_student_avg_scores(
        class_id=cid, subject_id=sub, semester_id=sem
    )

    buckets = [DistributionBucket(**b) for b in bucketize(scores)]
    mean = sum(scores) / len(scores) if scores else None
    return ClassDistributionResponse(
        buckets=buckets,
        total_students=len(scores),
        mean=mean,
        median=median(scores),
    )


@router.get("/teachers/me/dashboard", response_model=TeacherDashboardResponse)
async def get_teacher_dashboard(
    semester_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
    repo: TeacherDashboardRepo = Depends(get_teacher_dashboard_repo),
) -> TeacherDashboardResponse:
    sem = uuid.UUID(semester_id) if semester_id else await current_semester_id(db)

    cls_result = await db.execute(
        select(Class).where(
            Class.teacher_id == current_user.id,
            Class.school_id == current_user.school_id,
        )
    )
    classes = cls_result.scalars().all()
    class_ids = [c.id for c in classes]

    if class_ids:
        sc_result = await db.execute(
            select(Student.class_id, func.count(Student.id))
            .where(Student.class_id.in_(class_ids))
            .group_by(Student.class_id)
        )
        student_counts = {cid: int(n) for cid, n in sc_result.all()}
    else:
        student_counts = {}

    aggs = await repo.get_class_aggregates(class_ids=class_ids, semester_id=sem)
    agg_map = {a.class_id: a for a in aggs}

    window_start = dt.datetime.utcnow() - dt.timedelta(days=RECENT_FEEDBACK_WINDOW_DAYS)
    fb_result = await db.execute(
        select(func.count(Feedback.id)).where(
            Feedback.teacher_id == current_user.id,
            Feedback.created_at >= window_start,
        )
    )
    recent_feedbacks_count = int(fb_result.scalar_one() or 0)

    today = dt.date.today()
    cs_result = await db.execute(
        select(func.count(Counseling.id)).where(
            Counseling.teacher_id == current_user.id,
            Counseling.date > today,
        )
    )
    pending_counselings_count = int(cs_result.scalar_one() or 0)

    return TeacherDashboardResponse(
        classes=[
            TeacherDashboardClass(
                class_id=str(c.id),
                name=c.name,
                student_count=student_counts.get(c.id, 0),
                avg_score=agg_map[c.id].avg_score if c.id in agg_map else None,
                attendance_rate=agg_map[c.id].attendance_rate if c.id in agg_map else None,
            )
            for c in classes
        ],
        recent_feedbacks_count=recent_feedbacks_count,
        pending_counselings_count=pending_counselings_count,
    )
