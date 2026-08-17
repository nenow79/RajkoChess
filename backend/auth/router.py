import logging
import secrets
from typing import Annotated

from db.models import UserStatus
from db.session import get_db_session
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from rate_limit import clear_rate_limit, enforce_rate_limit, request_ip

from auth.cookies import clear_auth_cookies, set_auth_cookies, set_csrf_cookie
from auth.dependencies import CurrentAuth, csrf_cookie, get_current_auth, require_csrf
from auth.email import (
    EmailDeliveryError,
    send_password_reset_email,
    send_verification_email,
)
from auth.policies import all_effective_entitlements
from auth.plans import plan_summary
from auth.platform_accounts import (
    delete_platform_account,
    list_platform_accounts,
    platform_account_response,
    upsert_platform_account,
)
from auth.schemas import (
    CsrfResponse,
    EmailVerificationRequest,
    EmailVerificationResendRequest,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PlatformAccountRequest,
    PlatformAccountResponse,
    RegisterRequest,
    UserResponse,
)
from auth.security import generate_secret, hash_secret
from auth.service import (
    DuplicateEmailError,
    EmailNotVerifiedError,
    InactiveUserError,
    InvalidAuthTokenError,
    InvalidCredentialsError,
    authenticate_user,
    create_email_verification_token,
    create_password_reset_token,
    create_session,
    find_user_for_email_verification,
    find_user_for_password_reset,
    normalize_email,
    register_user,
    reset_password_with_token,
    revoke_all_user_sessions,
    revoke_session,
    supersede_email_verification_tokens,
    supersede_password_reset_tokens,
    verify_email_token,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    await enforce_rate_limit(
        bucket="register_ip",
        identity=request_ip(request),
        limit=5,
        window_seconds=3600,
    )
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
    created_token = await create_email_verification_token(db, user=user)
    try:
        await send_verification_email(recipient=user.email, token=created_token.token)
    except EmailDeliveryError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Konto zostało utworzone, ale wiadomość nie mogła zostać wysłana. "
                "Spróbuj wysłać link ponownie."
            ),
        )
    await supersede_email_verification_tokens(
        db, user_id=user.id, keep_token_id=created_token.model.id
    )
    return UserResponse.from_user(user)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LoginResponse:
    normalized_email = normalize_email(str(payload.email))
    await enforce_rate_limit(
        bucket="login_ip",
        identity=request_ip(request),
        limit=20,
        window_seconds=900,
        fail_closed=False,
    )
    await enforce_rate_limit(
        bucket="login_account",
        identity=normalized_email,
        limit=5,
        window_seconds=900,
        fail_closed=False,
    )
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
    except EmailNotVerifiedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Potwierdź adres e-mail przed zalogowaniem",
        )

    created = await create_session(
        db, user=user, user_agent=request.headers.get("user-agent")
    )
    set_auth_cookies(
        response,
        session_token=created.session_token,
        csrf_token=created.csrf_token,
    )
    await clear_rate_limit(bucket="login_account", identity=normalized_email)
    return LoginResponse(
        user=UserResponse.from_user(user), csrf_token=created.csrf_token
    )


@router.post("/email-verification/confirm", response_model=MessageResponse)
async def confirm_email(
    payload: EmailVerificationRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MessageResponse:
    try:
        await verify_email_token(db, token=payload.token)
    except InvalidAuthTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link potwierdzający jest nieprawidłowy, wygasł lub został już użyty",
        )
    return MessageResponse(message="Adres e-mail został potwierdzony")


@router.post("/email-verification/resend", response_model=MessageResponse)
async def resend_email_verification(
    payload: EmailVerificationResendRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MessageResponse:
    await enforce_rate_limit(
        bucket="verification_ip",
        identity=request_ip(request),
        limit=10,
        window_seconds=3600,
    )
    await enforce_rate_limit(
        bucket="verification_account",
        identity=str(payload.email),
        limit=3,
        window_seconds=3600,
    )
    generic_message = (
        "Jeśli konto istnieje i wymaga potwierdzenia, wysłaliśmy nowy link."
    )
    user = await find_user_for_email_verification(db, email=str(payload.email))
    if (
        user is None
        or user.email_verified_at is not None
        or user.status != UserStatus.ACTIVE
    ):
        return MessageResponse(message=generic_message)

    created_token = await create_email_verification_token(db, user=user)
    try:
        await send_verification_email(recipient=user.email, token=created_token.token)
    except EmailDeliveryError:
        logger.exception(
            "Nie udało się wysłać wiadomości weryfikacyjnej do użytkownika %s",
            user.id,
        )
        return MessageResponse(message=generic_message)
    await supersede_email_verification_tokens(
        db, user_id=user.id, keep_token_id=created_token.model.id
    )
    return MessageResponse(message=generic_message)


@router.post("/password-reset/request", response_model=MessageResponse)
async def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MessageResponse:
    await enforce_rate_limit(
        bucket="password_reset_ip",
        identity=request_ip(request),
        limit=10,
        window_seconds=3600,
    )
    await enforce_rate_limit(
        bucket="password_reset_account",
        identity=str(payload.email),
        limit=3,
        window_seconds=3600,
    )
    generic_message = (
        "Jeśli aktywne konto z tym adresem istnieje, wysłaliśmy link do zmiany hasła."
    )
    user = await find_user_for_password_reset(db, email=str(payload.email))
    if user is None:
        return MessageResponse(message=generic_message)

    created_token = await create_password_reset_token(db, user=user)
    try:
        await send_password_reset_email(recipient=user.email, token=created_token.token)
    except EmailDeliveryError:
        logger.exception(
            "Nie udało się wysłać wiadomości resetującej hasło użytkownika %s",
            user.id,
        )
        return MessageResponse(message=generic_message)
    await supersede_password_reset_tokens(
        db, user_id=user.id, keep_token_id=created_token.model.id
    )
    return MessageResponse(message=generic_message)


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MessageResponse:
    try:
        await reset_password_with_token(
            db, token=payload.token, new_password=payload.password
        )
    except InvalidAuthTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link do zmiany hasła jest nieprawidłowy, wygasł lub został już użyty",
        )
    return MessageResponse(
        message="Hasło zostało zmienione. Zaloguj się ponownie na wszystkich urządzeniach."
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


@router.get("/entitlements")
async def entitlements(
    current: Annotated[CurrentAuth, Depends(get_current_auth)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    return {"entitlements": await all_effective_entitlements(db, user=current.user)}


@router.get("/plan")
async def current_plan(
    current: Annotated[CurrentAuth, Depends(get_current_auth)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    return await plan_summary(db, user=current.user)


@router.get("/platform-accounts")
async def platform_accounts(
    current: Annotated[CurrentAuth, Depends(get_current_auth)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    models = await list_platform_accounts(db, user=current.user)
    return {"accounts": [platform_account_response(model) for model in models]}


@router.put(
    "/platform-accounts/{provider}", response_model=PlatformAccountResponse
)
async def save_platform_account(
    payload: PlatformAccountRequest,
    provider: Annotated[
        str, Path(min_length=1, max_length=32, pattern=r"^[a-z0-9_-]+$")
    ],
    current: Annotated[CurrentAuth, Depends(require_csrf)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    try:
        model = await upsert_platform_account(
            db,
            user=current.user,
            provider=provider,
            username=payload.username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return platform_account_response(model)


@router.delete("/platform-accounts/{provider}", response_model=MessageResponse)
async def remove_platform_account(
    provider: Annotated[
        str, Path(min_length=1, max_length=32, pattern=r"^[a-z0-9_-]+$")
    ],
    current: Annotated[CurrentAuth, Depends(require_csrf)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MessageResponse:
    try:
        await delete_platform_account(db, user=current.user, provider=provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MessageResponse(message="Usunięto zapisany login platformy")


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
