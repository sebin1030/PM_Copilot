"""Supabase access-token verification and request-scoped database credentials."""
from contextvars import ContextVar

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL, supabase_enabled


_bearer = HTTPBearer(auto_error=False)
_access_token: ContextVar[str | None] = ContextVar("access_token", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)


def current_access_token() -> str | None:
    return _access_token.get()


def current_user_id() -> str | None:
    return _user_id.get()


async def require_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """Verify with Supabase Auth; never accept an unverified browser user id."""
    if not supabase_enabled():
        yield {"id": "local-development"}
        return
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "apikey": SUPABASE_PUBLISHABLE_KEY,
                    "Authorization": f"Bearer {credentials.credentials}",
                },
            )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="로그인 세션이 만료되었습니다. 다시 로그인해 주세요.")
        user = response.json()
        if not isinstance(user.get("id"), str):
            raise HTTPException(status_code=401, detail="로그인 정보를 확인할 수 없습니다.")
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="로그인 서비스를 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.") from None

    token = _access_token.set(credentials.credentials)
    user_id = _user_id.set(user["id"])
    try:
        yield user
    finally:
        _access_token.reset(token)
        _user_id.reset(user_id)
