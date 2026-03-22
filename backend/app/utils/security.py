import datetime as dt
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def _create_token(payload: dict[str, Any], expires_delta: dt.timedelta) -> str:
    to_encode = payload.copy()
    expire = dt.datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(payload: dict[str, Any]) -> str:
    return _create_token(
        {**payload, "type": "access"},
        dt.timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(payload: dict[str, Any]) -> str:
    return _create_token(
        {**payload, "type": "refresh"},
        dt.timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None

