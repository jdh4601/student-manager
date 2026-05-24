from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.utils.security import decode_token

limiter = Limiter(key_func=get_remote_address)


def user_id_key(request: Request) -> str:
    """JWT `sub`(user_id) 기반 키. 토큰 없으면 IP로 폴백.

    Chat 등 인증 후 사용자 단위 quota를 적용할 때 `@limiter.limit(..., key_func=user_id_key)`로 주입한다.
    """
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        payload = decode_token(auth[7:])
        if payload and payload.get("sub"):
            return f"user:{payload['sub']}"
    return get_remote_address(request)

