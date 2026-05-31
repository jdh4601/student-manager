import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.config import settings
from app.errors import AppException
from app.models.user import User
from app.ratelimit import limiter
from app.schemas.auth import (
    InvitationAcceptRequest,
    InvitationPreviewResponse,
    LoginRequest,
    MeResponse,
    PasswordRecoveryRequest,
    PasswordRecoveryResponse,
    PasswordResetRequest,
    RefreshResponse,
    TokenResponse,
)
from app.services.auth import (
    accept_invitation,
    authenticate_user,
    create_tokens,
    get_invitation_by_token,
    get_refresh_cookie_max_age,
    issue_password_reset,
    reset_password,
)
from app.services.auth_delivery import build_frontend_auth_link, deliver_auth_link
from app.services.oauth import (
    GoogleOAuthClient,
    get_oauth_client,
    login_or_create_teacher,
)
from app.utils.security import create_access_token, decode_token, generate_opaque_token, hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=get_refresh_cookie_max_age(),
        path=settings.cookie_path,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(settings.refresh_cookie_name, path=settings.cookie_path)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise AppException(401, "이메일 또는 비밀번호가 올바르지 않습니다.", "AUTH_INVALID_CREDENTIALS")
    if not user.is_active:
        raise AppException(401, "비활성화된 계정입니다.", "AUTH_ACCOUNT_INACTIVE")
    access_token, refresh_token = create_tokens(user)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(
        access_token=access_token,
        role=user.role,
        user_id=str(user.id),
        name=user.name,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get(settings.refresh_cookie_name)
    if not token:
        raise AppException(401, "리프레시 토큰이 없습니다.", "AUTH_TOKEN_EXPIRED")
    payload = decode_token(token)
    if payload is None or payload.get("type") != "refresh":
        raise AppException(401, "리프레시 토큰이 만료되었습니다.", "AUTH_TOKEN_EXPIRED")

    result = await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None:
        raise AppException(401, "리프레시 토큰이 만료되었습니다.", "AUTH_TOKEN_EXPIRED")
    if not user.is_active:
        raise AppException(401, "비활성화된 계정입니다.", "AUTH_ACCOUNT_INACTIVE")

    access_token = create_access_token(
        {"sub": str(user.id), "role": user.role, "school_id": str(user.school_id)}
    )
    return RefreshResponse(access_token=access_token)


@router.post("/logout", status_code=204)
async def logout(response: Response):
    _clear_refresh_cookie(response)


@router.get("/oauth/google/login", summary="교사 Google OAuth 시작")
async def oauth_google_login(
    oauth: GoogleOAuthClient = Depends(get_oauth_client),
):
    """구글 동의 화면 authorize_url 발급. FE는 이 URL로 리다이렉트한다."""
    return {"authorize_url": oauth.authorize_url(state=generate_opaque_token())}


@router.get("/oauth/google/callback", response_model=TokenResponse, summary="교사 Google OAuth 콜백")
async def oauth_google_callback(
    code: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    oauth: GoogleOAuthClient = Depends(get_oauth_client),
):
    """code 교환 → edu 도메인 검증 → 교사 upsert → 토큰 발급."""
    profile = await oauth.exchange_code(code)
    user = await login_or_create_teacher(db, profile)
    if not user.is_active:
        raise AppException(401, "비활성화된 계정입니다.", "AUTH_ACCOUNT_INACTIVE")
    access_token, refresh_token = create_tokens(user)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(
        access_token=access_token,
        role=user.role,
        user_id=str(user.id),
        name=user.name,
    )


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        school_id=str(current_user.school_id),
    )


@router.get("/invitations/{token}", response_model=InvitationPreviewResponse)
async def get_invitation_preview(token: str, db: AsyncSession = Depends(get_db)):
    invitation, user = await get_invitation_by_token(db, token=token)
    return InvitationPreviewResponse(
        email=user.email,
        name=user.name,
        role=user.role,
        expires_at=invitation.expires_at.isoformat(),
    )


@router.post("/invitations/accept", response_model=TokenResponse)
async def accept_invitation_endpoint(
    body: InvitationAcceptRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await accept_invitation(db, token=body.token, password_hash=hash_password(body.password))
    access_token, refresh_token = create_tokens(user)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(
        access_token=access_token,
        role=user.role,
        user_id=str(user.id),
        name=user.name,
    )


@router.post("/password-recovery", response_model=PasswordRecoveryResponse)
async def password_recovery(
    body: PasswordRecoveryRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == str(body.email)))
    user = result.scalar_one_or_none()
    if user is None:
        return PasswordRecoveryResponse(accepted=True, delivery=settings.auth_link_delivery)

    reset_token = await issue_password_reset(db, user=user)
    link = build_frontend_auth_link("/forgot-password", reset_token)
    delivery = await deliver_auth_link(kind="password-recovery", recipient_email=user.email, link=link)
    return PasswordRecoveryResponse(accepted=True, delivery=delivery.delivery, preview_url=delivery.preview_url)


@router.post("/password-reset", status_code=204)
async def password_reset(
    body: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    await reset_password(db, token=body.token, password_hash=hash_password(body.password))
