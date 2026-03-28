import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.errors import AppException
from app.ratelimit import limiter
from app.models.user import User
from app.schemas.auth import LoginRequest, MeResponse, RefreshResponse, TokenResponse
from app.services.auth import authenticate_user, create_tokens
from app.utils.security import create_access_token, decode_token
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise AppException(401, "이메일 또는 비밀번호가 올바르지 않습니다.", "AUTH_INVALID_CREDENTIALS")
    if not user.is_active:
        raise AppException(401, "비활성화된 계정입니다.", "AUTH_ACCOUNT_INACTIVE")
    access_token, refresh_token = create_tokens(user)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=7 * 24 * 60 * 60,
    )
    return TokenResponse(
        access_token=access_token,
        role=user.role,
        user_id=str(user.id),
        name=user.name,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise AppException(401, "No refresh token", "AUTH_TOKEN_EXPIRED")
    payload = decode_token(token)
    if payload is None or payload.get("type") != "refresh":
        raise AppException(401, "Invalid refresh token", "AUTH_TOKEN_EXPIRED")

    result = await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppException(401, "비활성화된 계정입니다.", "AUTH_ACCOUNT_INACTIVE")

    access_token = create_access_token(
        {"sub": payload["sub"], "role": payload["role"], "school_id": payload["school_id"]}
    )
    return RefreshResponse(access_token=access_token)


@router.post("/logout", status_code=204)
async def logout(response: Response, _: User = Depends(get_current_user)):
    response.delete_cookie("refresh_token")


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        school_id=str(current_user.school_id),
    )
