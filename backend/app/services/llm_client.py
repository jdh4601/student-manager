"""LLM provider client.

기본은 OpenAI API를 OpenAI SDK로 호출한다.
OPENAI_API_KEY가 없거나 `LLM_PROVIDER=stub`이면 결정론적 stub으로 폴백한다.

Spec: docs/design-spec.md §10.4 — POST /api/v1/chat, timeout 10s, max_tokens 1024.
"""

from __future__ import annotations

from typing import Protocol

from app.config import settings
from app.errors import AppException


class LlmClient(Protocol):
    async def complete(self, *, system: str, user: str) -> str: ...


class StubLlmClient:
    """결정론적 echo provider. 테스트/키 없음 시 폴백."""

    async def complete(self, *, system: str, user: str) -> str:
        return f"[stub] ctx_chars={len(system)} msg={user[:80]}"


class OpenAiLlmClient:
    """OpenAI (or any OpenAI-compatible) endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_tokens: int,
    ) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout_seconds
        )
        self._model = model
        self._max_tokens = max_tokens

    async def complete(self, *, system: str, user: str) -> str:
        from openai import APIError, APITimeoutError

        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=self._max_tokens,
            )
        except APITimeoutError as exc:
            raise AppException(504, "LLM 응답 시간 초과", "CHAT_TIMEOUT") from exc
        except APIError as exc:
            raise AppException(502, "LLM 서비스 오류", "CHAT_UPSTREAM_ERROR") from exc

        return resp.choices[0].message.content or ""


def get_llm_client() -> LlmClient:
    """FastAPI dependency. 테스트는 `app.dependency_overrides`로 교체."""
    provider = settings.llm_provider
    if provider == "stub" or (provider == "auto" and not settings.openai_api_key):
        return StubLlmClient()
    if not settings.openai_api_key:
        raise AppException(503, "LLM 미설정", "CHAT_LLM_NOT_CONFIGURED")
    return OpenAiLlmClient(
        api_key=settings.openai_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_tokens,
    )
