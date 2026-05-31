"""SMS-63: POST /api/v1/chat 통합 테스트.

LLM provider와 컨텍스트 repo를 모두 dependency_overrides로 교체하여
순수 라우터 로직(RBAC, mask_context 호출, 토큰 복원)을 검증한다.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import User
from app.routers.chat import _resolve_chat_context_repo
from app.services.llm_client import get_llm_client
from app.utils.security import create_access_token, hash_password
from tests.conftest import async_session_test


class _FakeRepo:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.received_teacher_id: uuid.UUID | None = None
        self.received_semester_id: uuid.UUID | None = None

    async def fetch_student_rows(
        self, *, teacher_id, school_id, semester_id=None
    ):
        self.received_teacher_id = teacher_id
        self.received_semester_id = semester_id
        return list(self.rows)


class _FakeLlm:
    def __init__(self, *, reply: str = "ok") -> None:
        self.reply = reply
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def complete(self, *, system: str, user: str) -> str:
        self.last_system = system
        self.last_user = user
        return self.reply


def _override(repo, llm):
    app.dependency_overrides[_resolve_chat_context_repo] = lambda: repo
    app.dependency_overrides[get_llm_client] = lambda: llm


def _clear_overrides():
    app.dependency_overrides.pop(_resolve_chat_context_repo, None)
    app.dependency_overrides.pop(get_llm_client, None)


def _five_students(school_id) -> list[dict[str, Any]]:
    return [
        {
            "student_id": uuid.uuid4(),
            "student_name": f"학생원본{i}",
            "student_number": i,
            "class_name": "1-1",
        }
        for i in range(1, 6)
    ]


async def test_chat_happy_path_with_stub_llm(auth_client_teacher, seed_teacher):
    rows = _five_students(seed_teacher.school_id)
    repo = _FakeRepo(rows)
    llm = _FakeLlm(reply="응답입니다.")
    _override(repo, llm)
    try:
        resp = await auth_client_teacher.post(
            "/api/v1/chat", json={"message": "1-1 반 평균은?"}
        )
    finally:
        _clear_overrides()

    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "응답입니다."
    assert uuid.UUID(body["thread_id"])  # parseable
    assert body["referenced_students"] == []


async def test_chat_strips_pii_from_system_prompt(auth_client_teacher, seed_teacher):
    rows = _five_students(seed_teacher.school_id)
    repo = _FakeRepo(rows)
    llm = _FakeLlm()
    _override(repo, llm)
    try:
        await auth_client_teacher.post(
            "/api/v1/chat", json={"message": "분석 부탁"}
        )
    finally:
        _clear_overrides()

    assert llm.last_system is not None
    for row in rows:
        assert row["student_name"] not in llm.last_system
        assert str(row["student_id"]) not in llm.last_system
    # tokens should appear instead
    assert "학생A" in llm.last_system


async def test_chat_resolves_tokens_to_referenced_students(
    auth_client_teacher, seed_teacher
):
    rows = _five_students(seed_teacher.school_id)
    repo = _FakeRepo(rows)
    llm = _FakeLlm(reply="학생A와 학생C가 평균보다 낮습니다.")
    _override(repo, llm)
    try:
        resp = await auth_client_teacher.post(
            "/api/v1/chat", json={"message": "?"}
        )
    finally:
        _clear_overrides()

    body = resp.json()
    refs = body["referenced_students"]
    assert len(refs) == 2
    ref_names = {r["name"] for r in refs}
    assert ref_names == {rows[0]["student_name"], rows[2]["student_name"]}


async def test_chat_processes_small_sample(
    auth_client_teacher, seed_teacher
):
    """k≥5 가드 제거: 5명 미만이어도 거부하지 않고 LLM에 마스킹 후 전달한다."""
    rows = _five_students(seed_teacher.school_id)[:3]  # k=3
    repo = _FakeRepo(rows)
    llm = _FakeLlm(reply="학생A가 가장 높습니다.")
    _override(repo, llm)
    try:
        resp = await auth_client_teacher.post(
            "/api/v1/chat", json={"message": "이 반?"}
        )
    finally:
        _clear_overrides()

    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "학생A가 가장 높습니다."
    assert llm.last_user == "이 반?"  # LLM was called
    # 원본 식별 정보는 마스킹된다
    assert llm.last_system is not None
    for row in rows:
        assert row["student_name"] not in llm.last_system
    # 토큰이 실제 학생으로 복원된다
    assert body["referenced_students"][0]["name"] == rows[0]["student_name"]


async def test_chat_resolves_semester_from_ibeon_keyword(
    auth_client_teacher, seed_teacher
):
    """SMS-97 — '이번' → latest semester id reaches the repo."""
    from app.models import Semester

    async with async_session_test() as session:
        latest = Semester(year=2026, term=1)
        previous = Semester(year=2025, term=2)
        session.add_all([latest, previous])
        await session.commit()
        await session.refresh(latest)

    repo = _FakeRepo(_five_students(seed_teacher.school_id))
    _override(repo, _FakeLlm())
    try:
        await auth_client_teacher.post(
            "/api/v1/chat", json={"message": "이번 학기 영어 평균이 어때?"}
        )
    finally:
        _clear_overrides()

    assert repo.received_semester_id == latest.id


async def test_chat_resolves_semester_from_jinan_keyword(
    auth_client_teacher, seed_teacher
):
    """SMS-97 — '지난' → second-latest semester id reaches the repo."""
    from app.models import Semester

    async with async_session_test() as session:
        latest = Semester(year=2026, term=1)
        previous = Semester(year=2025, term=2)
        session.add_all([latest, previous])
        await session.commit()
        await session.refresh(previous)

    repo = _FakeRepo(_five_students(seed_teacher.school_id))
    _override(repo, _FakeLlm())
    try:
        await auth_client_teacher.post(
            "/api/v1/chat", json={"message": "지난 학기 평균과 비교"}
        )
    finally:
        _clear_overrides()

    assert repo.received_semester_id == previous.id


async def test_chat_falls_back_to_latest_when_no_keyword(
    auth_client_teacher, seed_teacher
):
    """SMS-97 — 학기 키워드 없으면 최신 학기로 폴백."""
    from app.models import Semester

    async with async_session_test() as session:
        latest = Semester(year=2026, term=1)
        session.add(latest)
        await session.commit()
        await session.refresh(latest)

    repo = _FakeRepo(_five_students(seed_teacher.school_id))
    _override(repo, _FakeLlm())
    try:
        await auth_client_teacher.post(
            "/api/v1/chat", json={"message": "우리 반 평균"}
        )
    finally:
        _clear_overrides()

    assert repo.received_semester_id == latest.id


async def test_chat_passes_subjects_and_overall_into_system_prompt(
    auth_client_teacher, seed_teacher
):
    """SMS-95 — fetch_student_rows now returns analytics aggregates per student;
    the masked system prompt must surface those numbers so the LLM can ground
    quantitative answers."""
    rows: list[dict[str, Any]] = []
    for i in range(1, 6):
        rows.append(
            {
                "student_id": uuid.uuid4(),
                "student_name": f"학생원본{i}",
                "student_number": i,
                "class_name": "1-1",
                "overall": {
                    "avg_score": 80.0 + i,
                    "subject_count": 3,
                    "attendance_present_rate": 0.95,
                    "feedback_count": 1,
                },
                "subjects": [
                    {
                        "name": "영어",
                        "avg_score": 78.0 + i,
                        "max_score": 92.0,
                        "min_score": 60.0,
                        "latest_rank": 4,
                        "sample_count": 5,
                    },
                ],
            }
        )
    repo = _FakeRepo(rows)
    llm = _FakeLlm()
    _override(repo, llm)
    try:
        await auth_client_teacher.post(
            "/api/v1/chat", json={"message": "이번 학기 영어 평균이 어때?"}
        )
    finally:
        _clear_overrides()

    assert llm.last_system is not None
    # Quantitative grounding survives masking
    assert "영어" in llm.last_system
    assert "avg_score" in llm.last_system
    assert "subjects" in llm.last_system
    assert "overall" in llm.last_system


async def test_chat_preserves_thread_id_when_provided(
    auth_client_teacher, seed_teacher
):
    rows = _five_students(seed_teacher.school_id)
    given = str(uuid.uuid4())
    _override(_FakeRepo(rows), _FakeLlm(reply="ok"))
    try:
        resp = await auth_client_teacher.post(
            "/api/v1/chat", json={"thread_id": given, "message": "hi"}
        )
    finally:
        _clear_overrides()

    assert resp.json()["thread_id"] == given


async def test_chat_requires_authentication(client):
    resp = await client.post("/api/v1/chat", json={"message": "hi"})
    assert resp.status_code == 401


async def test_chat_rejects_student_role(seed_school):
    async with async_session_test() as session:
        student_user = User(
            school_id=seed_school.id,
            email="kid@test.com",
            hashed_password=hash_password("password123"),
            role="student",
            name="학생일",
        )
        session.add(student_user)
        await session.commit()
        await session.refresh(student_user)

    token = create_access_token(
        {
            "sub": str(student_user.id),
            "role": student_user.role,
            "school_id": str(student_user.school_id),
        }
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        resp = await c.post("/api/v1/chat", json={"message": "hi"})
    assert resp.status_code == 403


@pytest.mark.parametrize("bad", ["", "x" * 1001])
async def test_chat_rejects_invalid_message_length(auth_client_teacher, bad):
    resp = await auth_client_teacher.post(
        "/api/v1/chat", json={"message": bad}
    )
    assert resp.status_code == 422
