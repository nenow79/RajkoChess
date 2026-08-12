import secrets
from dataclasses import dataclass
from typing import Annotated

from db.models import AuthSession, User
from db.session import get_db_session
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import APIKeyCookie
from settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession

from auth.roles import ensure_admin
from auth.security import hash_secret
from auth.service import find_active_session

settings = get_settings()
session_cookie = APIKeyCookie(
    name=settings.auth_cookie_name,
    scheme_name="SessionCookie",
    auto_error=False,
)
csrf_cookie = APIKeyCookie(
    name=settings.auth_csrf_cookie_name,
    scheme_name="CsrfCookie",
    auto_error=False,
)


@dataclass(frozen=True)
class CurrentAuth:
    session: AuthSession
    user: User


async def get_current_auth(
    session_token: Annotated[str | None, Depends(session_cookie)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> CurrentAuth:
    model = await find_active_session(db, session_token) if session_token else None
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wymagane jest zalogowanie",
            headers={"WWW-Authenticate": "Session"},
        )
    return CurrentAuth(session=model, user=model.user)


async def require_csrf(
    current: Annotated[CurrentAuth, Depends(get_current_auth)],
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    csrf_cookie_value: Annotated[str | None, Depends(csrf_cookie)] = None,
) -> CurrentAuth:
    valid = bool(
        csrf_header
        and csrf_cookie_value
        and secrets.compare_digest(csrf_header, csrf_cookie_value)
        and secrets.compare_digest(
            hash_secret(csrf_header), current.session.csrf_token_hash
        )
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nieprawidłowy token CSRF",
        )
    return current


async def require_admin(
    current: Annotated[CurrentAuth, Depends(get_current_auth)],
) -> CurrentAuth:
    return ensure_admin(current)


async def require_admin_write(
    current: Annotated[CurrentAuth, Depends(require_csrf)],
) -> CurrentAuth:
    return ensure_admin(current)
