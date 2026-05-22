"""Chat 컨텍스트 빌더.

교사가 담당한 클래스의 학생 행을 LLM 컨텍스트용 dict 리스트로 반환한다.
각 행은 `overall` (전체 평균/출석률 등)과 `subjects` (과목별 평균/표본수)를
포함해 LLM이 정량 답변을 할 수 있도록 한다. PII는 호출자가 `mask_context()`로
다시 한 번 마스킹한다.

Spec: docs/design-spec.md §10.2, §10.3 / architecture.md §4.3.
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.analytics import get_student_overview_repo
from app.models.class_ import Class
from app.models.student import Student
from app.models.user import User
from app.services.analytics_query import (
    OverallRow,
    StudentOverviewRepo,
    SubjectRow,
)


class ChatContextRepo(Protocol):
    async def fetch_student_rows(
        self,
        *,
        teacher_id: uuid.UUID,
        school_id: uuid.UUID,
        semester_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]: ...


def _overall_to_dict(row: OverallRow) -> dict[str, Any]:
    return dataclasses.asdict(row)


def _subject_to_dict(row: SubjectRow) -> dict[str, Any]:
    d = dataclasses.asdict(row)
    # subject_id is a UUID — keep as string so the dict is JSON-serializable
    # without a custom encoder. SMS-96 will drop the field entirely.
    d["subject_id"] = str(d["subject_id"])
    return d


class PostgresChatContextRepo:
    """담임 학급 학생 + analytics 집계를 LLM 컨텍스트 dict로 빌드한다.

    학생 N명에 대해 두 번의 SQL(전체 + 과목별)로 끝내 N+1을 피한다.
    """

    def __init__(
        self, db: AsyncSession, overview_repo: StudentOverviewRepo
    ) -> None:
        self._db = db
        self._overview = overview_repo

    async def fetch_student_rows(
        self,
        *,
        teacher_id: uuid.UUID,
        school_id: uuid.UUID,
        semester_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        # Student 모델에는 name/school_id가 없다 — User JOIN으로 얻는다.
        # (학생의 PII는 User 테이블에 있고 Student는 학적 정보만 갖는다.)
        stmt = (
            select(Student, User, Class.name)
            .join(User, Student.user_id == User.id)
            .join(Class, Student.class_id == Class.id)
            .where(Class.teacher_id == teacher_id, User.school_id == school_id)
        )
        result = await self._db.execute(stmt)
        students = list(result.all())
        student_ids = [s.id for s, _u, _ in students]

        overall_map = await self._overview.get_overall_batch(
            student_ids=student_ids, semester_id=semester_id
        )
        subjects_map = await self._overview.get_subjects_batch(
            student_ids=student_ids, semester_id=semester_id
        )

        rows: list[dict[str, Any]] = []
        for student, user, class_name in students:
            overall = overall_map.get(student.id)
            subjects = subjects_map.get(student.id, [])
            rows.append(
                {
                    "student_id": student.id,
                    "student_name": user.name,
                    "student_number": student.student_number,
                    "class_name": class_name,
                    "overall": _overall_to_dict(overall) if overall else None,
                    "subjects": [_subject_to_dict(s) for s in subjects],
                }
            )
        return rows


def get_chat_context_repo(
    db: AsyncSession,
    overview_repo: StudentOverviewRepo | None = None,
) -> ChatContextRepo:
    if overview_repo is None:
        overview_repo = get_student_overview_repo(db)
    return PostgresChatContextRepo(db, overview_repo)
