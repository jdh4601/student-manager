"""POST /api/v1/chat — 교사용 분석 챗봇 (REQ-080, REQ-081, Spec §10.4).

흐름: 컨텍스트 조회 → `mask_context` (k≥5) → system prompt 구성 →
LLM 호출 → 응답 후처리(토큰 → 실제 학생).
"""

import json
import re
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import require_role
from app.dependencies.db import get_db
from app.models.user import User
from app.ratelimit import limiter, user_id_key
from app.schemas.chat import ChatRequest, ChatResponse, StudentRef
from app.services.chat_context import ChatContextRepo, get_chat_context_repo
from app.services.chat_intent import resolve_semester_id
from app.services.llm_client import LlmClient, get_llm_client
from app.services.llm_sanitizer import SmallSampleError, mask_context

router = APIRouter(prefix="/chat", tags=["chat"])

_TOKEN_PATTERN = re.compile(r"학생[A-Z]{1,2}")

_SYSTEM_PROMPT = (
    "당신은 한국어 학교 데이터 분석 비서입니다. "
    "아래 마스킹된 학급 통계만을 근거로 답하세요. "
    "마스킹된 토큰(학생A, 학생B…) 외의 학생명을 임의로 만들어내지 마세요."
)

_SMALL_SAMPLE_REPLY = (
    "개인 식별을 막기 위해 5명 미만 표본에 대한 분석은 거부합니다."
)


def _resolve_chat_context_repo(
    db: AsyncSession = Depends(get_db),
) -> ChatContextRepo:
    return get_chat_context_repo(db)


@router.post("", response_model=ChatResponse)
@limiter.limit("10/minute", key_func=user_id_key)
async def post_chat(
    request: Request,
    body: ChatRequest,
    user: User = Depends(require_role("teacher")),
    repo: ChatContextRepo = Depends(_resolve_chat_context_repo),
    llm: LlmClient = Depends(get_llm_client),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    semester_id = await resolve_semester_id(body.message, db)
    rows = await repo.fetch_student_rows(
        teacher_id=user.id,
        school_id=user.school_id,
        semester_id=semester_id,
    )

    name_by_id = {row["student_id"]: row["student_name"] for row in rows}

    try:
        masked_rows, token_map = mask_context(rows)
    except SmallSampleError:
        return ChatResponse(
            thread_id=body.thread_id or uuid.uuid4(),
            reply=_SMALL_SAMPLE_REPLY,
            referenced_students=[],
        )

    system_prompt = (
        f"{_SYSTEM_PROMPT}\n\n[학급 통계]\n"
        + json.dumps(masked_rows, ensure_ascii=False, default=str)
    )

    reply = await llm.complete(system=system_prompt, user=body.message)

    referenced: list[StudentRef] = []
    seen: set[str] = set()
    for token in _TOKEN_PATTERN.findall(reply):
        if token in seen:
            continue
        seen.add(token)
        student_id = token_map.get(token)
        if student_id is None:
            continue
        name = name_by_id.get(student_id)
        if name is None:
            continue
        referenced.append(StudentRef(id=student_id, name=name))

    return ChatResponse(
        thread_id=body.thread_id or uuid.uuid4(),
        reply=reply,
        referenced_students=referenced,
    )
