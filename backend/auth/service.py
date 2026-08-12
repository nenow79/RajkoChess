from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from db.models import AuthSession, AuthToken, AuthTokenType, Identity, User, UserStatus
from settings import get_settings
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from auth.security import (
    DUMMY_PASSWORD_HASH,
    generate_secret,
    hash_password,
    hash_secret,
    verify_password,
)

PASSWORD_PROVIDER = "password"
ACTIVITY_UPDATE_INTERVAL = timedelta(minutes=15)


class DuplicateEmailError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class EmailNotVerifiedError(Exception):
    pass


class InvalidAuthTokenError(Exception):
    pass


@dataclass(frozen=True)
class CreatedSession:
    model: AuthSession
    session_token: str
    csrf_token: str


@dataclass(frozen=True)
class CreatedAuthToken:
    model: AuthToken
    token: str


def normalize_email(email: str) -> str:
    return email.strip().casefold()


async def register_user(
    db: AsyncSession, *, email: str, password: str, display_name: str | None
) -> User:
    normalized_email = normalize_email(email)
    existing = await db.scalar(select(User.id).where(User.email == normalized_email))
    if existing is not None:
        raise DuplicateEmailError

    password_digest = await hash_password(password)
    user = User(email=normalized_email, display_name=display_name)
    user.identities.append(
        Identity(
            provider=PASSWORD_PROVIDER,
            provider_subject=normalized_email,
            password_hash=password_digest,
        )
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicateEmailError from exc
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, *, email: str, password: str) -> User:
    normalized_email = normalize_email(email)
    identity = await db.scalar(
        select(Identity)
        .options(joinedload(Identity.user))
        .where(
            Identity.provider == PASSWORD_PROVIDER,
            Identity.provider_subject == normalized_email,
        )
    )

    password_digest = (
        identity.password_hash
        if identity and identity.password_hash
        else DUMMY_PASSWORD_HASH
    )
    verified, updated_hash = await verify_password(password, password_digest)
    if identity is None or not verified:
        raise InvalidCredentialsError
    if identity.user.status != UserStatus.ACTIVE:
        raise InactiveUserError
    if identity.user.email_verified_at is None:
        raise EmailNotVerifiedError

    if updated_hash is not None:
        identity.password_hash = updated_hash
        await db.commit()
    return identity.user


async def create_email_verification_token(
    db: AsyncSession, *, user: User
) -> CreatedAuthToken:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    token = generate_secret()
    model = AuthToken(
        user_id=user.id,
        type=AuthTokenType.EMAIL_VERIFICATION,
        token_hash=hash_secret(token),
        created_at=now,
        expires_at=now + timedelta(hours=settings.email_verification_hours),
    )
    db.add(model)
    await db.commit()
    return CreatedAuthToken(model=model, token=token)


async def supersede_email_verification_tokens(
    db: AsyncSession, *, user_id, keep_token_id
) -> None:
    await db.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user_id,
            AuthToken.type == AuthTokenType.EMAIL_VERIFICATION,
            AuthToken.id != keep_token_id,
            AuthToken.consumed_at.is_(None),
        )
        .values(consumed_at=datetime.now(timezone.utc))
    )
    await db.commit()


async def verify_email_token(db: AsyncSession, *, token: str) -> User:
    now = datetime.now(timezone.utc)
    model = await db.scalar(
        select(AuthToken)
        .options(joinedload(AuthToken.user))
        .where(
            AuthToken.token_hash == hash_secret(token),
            AuthToken.type == AuthTokenType.EMAIL_VERIFICATION,
        )
        .with_for_update(of=AuthToken)
    )
    if model is None or model.consumed_at is not None or model.expires_at <= now:
        raise InvalidAuthTokenError

    await db.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == model.user_id,
            AuthToken.type == AuthTokenType.EMAIL_VERIFICATION,
            AuthToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    model.consumed_at = now
    if model.user.email_verified_at is None:
        model.user.email_verified_at = now
    await db.commit()
    return model.user


async def find_user_for_email_verification(
    db: AsyncSession, *, email: str
) -> User | None:
    return await db.scalar(select(User).where(User.email == normalize_email(email)))


async def create_session(
    db: AsyncSession, *, user: User, user_agent: str | None
) -> CreatedSession:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    absolute_expires_at = now + timedelta(days=settings.auth_session_absolute_days)
    expires_at = min(
        now + timedelta(days=settings.auth_session_idle_days), absolute_expires_at
    )
    session_token = generate_secret()
    csrf_token = generate_secret()
    model = AuthSession(
        user_id=user.id,
        token_hash=hash_secret(session_token),
        csrf_token_hash=hash_secret(csrf_token),
        created_at=now,
        last_seen_at=now,
        expires_at=expires_at,
        absolute_expires_at=absolute_expires_at,
        user_agent=(user_agent or "")[:512] or None,
    )
    db.add(model)
    await db.commit()
    return CreatedSession(
        model=model, session_token=session_token, csrf_token=csrf_token
    )


async def find_active_session(
    db: AsyncSession, session_token: str
) -> AuthSession | None:
    now = datetime.now(timezone.utc)
    model = await db.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user))
        .where(AuthSession.token_hash == hash_secret(session_token))
    )
    if (
        model is None
        or model.revoked_at is not None
        or model.expires_at <= now
        or model.absolute_expires_at <= now
        or model.user.status != UserStatus.ACTIVE
    ):
        return None

    if model.last_seen_at <= now - ACTIVITY_UPDATE_INTERVAL:
        settings = get_settings()
        model.last_seen_at = now
        model.expires_at = min(
            now + timedelta(days=settings.auth_session_idle_days),
            model.absolute_expires_at,
        )
        await db.commit()
    return model


async def revoke_session(
    db: AsyncSession, session: AuthSession, *, reason: str
) -> None:
    session.revoked_at = datetime.now(timezone.utc)
    session.revoked_reason = reason[:80]
    await db.commit()


async def revoke_all_user_sessions(db: AsyncSession, *, user_id) -> int:
    result = await db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(
            revoked_at=datetime.now(timezone.utc),
            revoked_reason="logout_all",
        )
    )
    await db.commit()
    return cast(CursorResult[Any], result).rowcount or 0
