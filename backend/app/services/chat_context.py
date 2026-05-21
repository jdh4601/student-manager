"""Chat 컨텍스트 빌더.

교사가 담당한 클래스의 학생 통계를 한 줄씩 dict로 반환한다.
실제 LLM 호출 전 `mask_context()`로 PII가 제거된다.

Spec: docs/design-spec.md §10.2, §10.3.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import Class
from app.models.student import Student


class ChatContextRepo(Protocol):
    async def fetch_student_rows(
        self, *, teacher_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[dict[str, Any]]: ...


class SqlChatContextRepo:
    """기본 구현: 담임 학생 + 학급을 반환한다.

    분석 집계 컬럼(avg_score 등)은 추후 별도 이슈에서 join 예정.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def fetch_student_rows(
        self, *, teacher_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        stmt = (
            select(Student, Class.name)
            .join(Class, Student.class_id == Class.id)
            .where(Class.teacher_id == teacher_id, Student.school_id == school_id)
        )
        result = await self._db.execute(stmt)
        return [
            {
                "student_id": student.id,
                "student_name": student.name,
                "student_number": student.student_number,
                "class_name": class_name,
            }
            for student, class_name in result.all()
        ]


def get_chat_context_repo(db: AsyncSession) -> ChatContextRepo:
    return SqlChatContextRepo(db)
