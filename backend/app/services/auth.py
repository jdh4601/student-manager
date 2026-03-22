from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.security import create_access_token, create_refresh_token, verify_password


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_tokens(user: User) -> Tuple[str, str]:
    payload = {"sub": str(user.id), "role": user.role, "school_id": str(user.school_id)}
    access = create_access_token(payload)
    refresh = create_refresh_token(payload)
    return access, refresh

