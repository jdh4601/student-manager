"""교사 Google OAuth (REQ-001 보강).

설계:
- `LlmClient`/`StubLlmClient`와 동일한 DI 패턴 — `GoogleOAuthClient` Protocol +
  `StubGoogleOAuthClient`(결정론, 네트워크 X) + `RealGoogleOAuthClient`.
- 보안 핵심: edu 도메인 화이트리스트로 교사 권한을 게이트. email_verified 강제.
- 신규 교사는 `oauth_default_school_id` 학교에 생성 (데모). 운영은 School.domain 매핑.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppException
from app.models.user import User
from app.utils.security import generate_opaque_token, hash_password

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


@dataclass(frozen=True)
class OAuthProfile:
    email: str
    name: str
    email_verified: bool


class GoogleOAuthClient(Protocol):
    def authorize_url(self, state: str) -> str: ...

    async def exchange_code(self, code: str) -> OAuthProfile: ...


class StubGoogleOAuthClient:
    """결정론 stub — `code`를 이메일로 해석해 검증된 프로필 반환 (테스트/데모)."""

    def authorize_url(self, state: str) -> str:
        # 데모에서 FE 없이도 흐름을 보이도록 callback을 직접 가리킨다.
        params = {"state": state, "code": "demo-teacher@allowed.edu"}
        return f"{settings.google_redirect_uri}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> OAuthProfile:
        email = code.strip().lower()
        local = email.split("@", 1)[0] if "@" in email else email
        return OAuthProfile(email=email, name=local, email_verified=True)


class RealGoogleOAuthClient:
    """실제 Google Authorization Code 교환 → userinfo 조회."""

    def authorize_url(self, state: str) -> str:
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        # 허용 도메인이 단 하나면 hd 힌트로 계정 선택창을 해당 Workspace 도메인으로 좁힌다.
        # 이는 UX 힌트일 뿐 — 실제 방어는 login_or_create_teacher의 서버측 도메인 게이트다.
        if len(settings.allowed_teacher_domains) == 1:
            params["hd"] = settings.allowed_teacher_domains[0]
        return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> OAuthProfile:
        async with httpx.AsyncClient(timeout=10.0) as http:
            token_res = await http.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_res.status_code != 200:
                raise AppException(401, "구글 인증에 실패했습니다.", "AUTH_OAUTH_EXCHANGE_FAILED")
            access_token = token_res.json().get("access_token")
            info_res = await http.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if info_res.status_code != 200:
                raise AppException(401, "구글 사용자 정보를 가져오지 못했습니다.", "AUTH_OAUTH_USERINFO_FAILED")
        info = info_res.json()
        return OAuthProfile(
            email=str(info.get("email", "")).lower(),
            name=info.get("name") or str(info.get("email", "")).split("@", 1)[0],
            email_verified=bool(info.get("email_verified", False)),
        )


def _stub_permitted() -> bool:
    """stub OAuth는 인증 우회가 가능 → 비-production 또는 명시적 허용일 때만."""
    return settings.environment != "production" or settings.allow_oauth_stub


def _require_stub() -> GoogleOAuthClient:
    if not _stub_permitted():
        # production에서 자격증명 없이 stub로 폴백 = 인증 우회. 명시적으로 거부.
        raise AppException(
            503,
            "OAuth가 구성되지 않았습니다. 관리자에게 문의하세요.",
            "AUTH_OAUTH_NOT_CONFIGURED",
        )
    return StubGoogleOAuthClient()


def get_oauth_client() -> GoogleOAuthClient:
    """provider 설정에 따라 stub/real 선택 (LLM 클라이언트와 동일 패턴)."""
    provider = settings.oauth_provider
    if provider == "stub":
        return _require_stub()
    if provider == "real" or (provider == "auto" and settings.google_client_id):
        return RealGoogleOAuthClient()
    # auto + 자격증명 없음 → stub 폴백은 production에서 차단됨.
    return _require_stub()


def _domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower() if "@" in email else ""


async def login_or_create_teacher(db: AsyncSession, profile: OAuthProfile) -> User:
    """OAuth 프로필을 교사 계정으로 매핑. 도메인 게이트 + 중복 없는 upsert."""
    if not profile.email_verified:
        raise AppException(403, "구글 이메일 인증이 완료되지 않았습니다.", "AUTH_OAUTH_EMAIL_UNVERIFIED")

    if _domain_of(profile.email) not in settings.allowed_teacher_domains:
        raise AppException(
            403,
            "교사 가입이 허용된 학교 도메인이 아닙니다.",
            "AUTH_OAUTH_DOMAIN_NOT_ALLOWED",
        )

    existing = await db.execute(select(User).where(User.email == profile.email))
    user = existing.scalar_one_or_none()
    if user is not None:
        return user  # 기존 계정 로그인 — 중복 생성 금지

    if settings.oauth_default_school_id is None:
        raise AppException(409, "배정 가능한 학교가 없습니다.", "AUTH_OAUTH_NO_SCHOOL")

    user = User(
        school_id=uuid.UUID(settings.oauth_default_school_id),
        email=profile.email,
        # OAuth 계정은 비밀번호 로그인 불가 — 추측 불가능한 무작위 해시.
        hashed_password=hash_password(generate_opaque_token()),
        role="teacher",
        name=profile.name,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
