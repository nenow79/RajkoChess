import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.cookies import clear_auth_cookies, set_auth_cookies, set_csrf_cookie
from auth.dependencies import CurrentAuth, csrf_cookie, get_current_auth, require_csrf
from auth.schemas import (
    CsrfResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RegisterRequest,
    UserResponse,
)
from auth.security import generate_secret, hash_secret
from auth.service import (
    DuplicateEmailError,
    InactiveUserError,
    InvalidCredentialsError,
    authenticate_user,
    create_session,
    register_user,
    revoke_all_user_sessions,
    revoke_session,
)
from db.session import get_db_session


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    try:
        user = await register_user(
            db,
            email=str(payload.email),
            password=payload.password,
            display_name=payload.display_name,
        )
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Konto z tym adresem e-mail już istnieje",
        )
    return UserResponse.from_user(user)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LoginResponse:
    try:
        user = await authenticate_user(
            db, email=str(payload.email), password=payload.password
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy e-mail lub hasło",
            headers={"WWW-Authenticate": "Session"},
        )
    except InactiveUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Konto jest nieaktywne",
        )

    created = await create_session(
        db, user=user, user_agent=request.headers.get("user-agent")
    )
    set_auth_cookies(
        response,
        session_token=created.session_token,
        csrf_token=created.csrf_token,
    )
    return LoginResponse(
        user=UserResponse.from_user(user), csrf_token=created.csrf_token
    )


@router.get("/me", response_model=UserResponse)
async def me(
    current: Annotated[CurrentAuth, Depends(get_current_auth)],
) -> UserResponse:
    return UserResponse.from_user(current.user)


@router.get("/csrf", response_model=CsrfResponse)
async def get_csrf_token(
    response: Response,
    current: Annotated[CurrentAuth, Depends(get_current_auth)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_csrf: Annotated[str | None, Depends(csrf_cookie)] = None,
) -> CsrfResponse:
    if current_csrf and secrets_compare_hash(
        current_csrf, current.session.csrf_token_hash
    ):
        return CsrfResponse(csrf_token=current_csrf)

    new_csrf = generate_secret()
    current.session.csrf_token_hash = hash_secret(new_csrf)
    await db.commit()
    set_csrf_cookie(response, csrf_token=new_csrf)
    return CsrfResponse(csrf_token=new_csrf)


def secrets_compare_hash(secret: str, expected_hash: bytes) -> bool:
    return secrets.compare_digest(hash_secret(secret), expected_hash)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    current: Annotated[CurrentAuth, Depends(require_csrf)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LogoutResponse:
    await revoke_session(db, current.session, reason="logout")
    clear_auth_cookies(response)
    return LogoutResponse()


@router.post("/logout-all", response_model=LogoutResponse)
async def logout_all(
    response: Response,
    current: Annotated[CurrentAuth, Depends(require_csrf)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LogoutResponse:
    count = await revoke_all_user_sessions(db, user_id=current.user.id)
    clear_auth_cookies(response)
    return LogoutResponse(revoked_sessions=count)
