"""SMS-64: /chat 교사당 분당 10회 rate limit + Retry-After."""

from __future__ import annotations

import uuid

import pytest

from app.main import app
from app.ratelimit import limiter
from app.routers.chat import _resolve_chat_context_repo
from app.services.llm_client import get_llm_client


class _StubRepo:
    async def fetch_student_rows(self, *, teacher_id, school_id):
        return [
            {
                "student_id": uuid.uuid4(),
                "student_name": f"학생원본{i}",
                "student_number": i,
                "class_name": "1-1",
            }
            for i in range(1, 6)
        ]


class _StubLlm:
    async def complete(self, *, system: str, user: str) -> str:
        return "ok"


@pytest.fixture
def stub_chat_deps():
    app.dependency_overrides[_resolve_chat_context_repo] = lambda: _StubRepo()
    app.dependency_overrides[get_llm_client] = lambda: _StubLlm()
    limiter.reset()
    try:
        yield
    finally:
        app.dependency_overrides.pop(_resolve_chat_context_repo, None)
        app.dependency_overrides.pop(get_llm_client, None)
        limiter.reset()


async def test_chat_allows_ten_requests_per_minute(
    auth_client_teacher, stub_chat_deps
):
    for _ in range(10):
        resp = await auth_client_teacher.post(
            "/api/v1/chat", json={"message": "hi"}
        )
        assert resp.status_code == 200


async def test_chat_rejects_eleventh_request_with_retry_after(
    auth_client_teacher, stub_chat_deps
):
    for _ in range(10):
        ok = await auth_client_teacher.post(
            "/api/v1/chat", json={"message": "hi"}
        )
        assert ok.status_code == 200

    over = await auth_client_teacher.post(
        "/api/v1/chat", json={"message": "hi"}
    )
    assert over.status_code == 429
    body = over.json()
    assert body["code"] == "RATE_LIMITED"
    assert "Retry-After" in over.headers
    assert int(over.headers["Retry-After"]) >= 1


async def test_chat_rate_limit_is_per_user(
    auth_client_teacher, auth_client_teacher_other, stub_chat_deps
):
    # Teacher A burns through quota
    for _ in range(10):
        resp = await auth_client_teacher.post(
            "/api/v1/chat", json={"message": "hi"}
        )
        assert resp.status_code == 200
    blocked = await auth_client_teacher.post(
        "/api/v1/chat", json={"message": "hi"}
    )
    assert blocked.status_code == 429

    # Teacher B still has full quota
    other = await auth_client_teacher_other.post(
        "/api/v1/chat", json={"message": "hi"}
    )
    assert other.status_code == 200
