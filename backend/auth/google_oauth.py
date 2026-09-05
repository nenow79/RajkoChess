from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode

import httpx
from db.models import Identity, User, UserStatus
from fastapi.concurrency import run_in_threadpool
from settings import get_settings
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from auth.service import normalize_email

GOOGLE_PROVIDER = "google"
GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


class GoogleOAuthError(Exception):
    pass


class GoogleAccountLinkRequiredError(GoogleOAuthError):
    pass


class GoogleIdentityConflictError(GoogleOAuthError):
    pass


class GoogleEmailMismatchError(GoogleOAuthError):
    pass


class InactiveGoogleUserError(GoogleOAuthError):
    pass


@dataclass(frozen=True)
class GoogleClaims:
    subject: str
    email: str
    display_name: str | None


def build_authorization_url(*, state: str, nonce: str, code_verifier: str) -> str:
    settings = get_settings()
    settings.require_google_oauth()
    query = urlencode(
        {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode("ascii")).digest()
            ).rstrip(b"=").decode("ascii"),
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    )
    return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{query}"


def _verify_id_token(raw_token: str, client_id: str) -> Mapping[str, Any]:
    # Import jest lokalny, aby wyłączenie Google OAuth nie blokowało startu aplikacji.
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(
        raw_token,
        google_requests.Request(),
        client_id,
    )


async def exchange_code_for_claims(
    *, code: str, expected_nonce: str, code_verifier: str
) -> GoogleClaims:
    settings = get_settings()
    settings.require_google_oauth()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret.get_secret_value(),
                    "redirect_uri": settings.google_oauth_redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": code_verifier,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GoogleOAuthError("Nie udało się wymienić kodu Google") from exc

    if not isinstance(payload, dict):
        raise GoogleOAuthError("Odpowiedź Google ma nieprawidłowy format")
    raw_id_token = payload.get("id_token")
    if not isinstance(raw_id_token, str) or not raw_id_token:
        raise GoogleOAuthError("Odpowiedź Google nie zawiera tokenu ID")
    try:
        claims = await run_in_threadpool(
            _verify_id_token, raw_id_token, settings.google_oauth_client_id
        )
    except Exception as exc:
        raise GoogleOAuthError("Token ID Google jest nieprawidłowy") from exc

    nonce = claims.get("nonce")
    subject = claims.get("sub")
    email = claims.get("email")
    if not isinstance(nonce, str) or not secrets.compare_digest(nonce, expected_nonce):
        raise GoogleOAuthError("Nieprawidłowy nonce Google")
    if not isinstance(subject, str) or not subject or len(subject) > 320:
        raise GoogleOAuthError("Brak prawidłowego identyfikatora konta Google")
    if not isinstance(email, str) or not email or claims.get("email_verified") is not True:
        raise GoogleOAuthError("Google nie potwierdził adresu e-mail")

    display_name = claims.get("name")
    if not isinstance(display_name, str):
        display_name = None
    elif len(display_name.strip()) > 80:
        display_name = display_name.strip()[:80]
    else:
        display_name = display_name.strip() or None
    return GoogleClaims(
        subject=subject,
        email=normalize_email(email),
        display_name=display_name,
    )


async def login_or_register_google_user(
    db: AsyncSession, *, claims: GoogleClaims
) -> User:
    identity = await db.scalar(
        select(Identity)
        .options(joinedload(Identity.user))
        .where(
            Identity.provider == GOOGLE_PROVIDER,
            Identity.provider_subject == claims.subject,
        )
    )
    if identity is not None:
        if identity.user.status != UserStatus.ACTIVE:
            raise InactiveGoogleUserError
        return identity.user

    existing_user = await db.scalar(select(User).where(User.email == claims.email))
    if existing_user is not None:
        raise GoogleAccountLinkRequiredError

    now = datetime.now(timezone.utc)
    user = User(
        email=claims.email,
        display_name=claims.display_name,
        email_verified_at=now,
    )
    user.identities.append(
        Identity(
            provider=GOOGLE_PROVIDER,
            provider_subject=claims.subject,
            password_hash=None,
        )
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise GoogleAccountLinkRequiredError from exc
    await db.refresh(user)
    return user


async def link_google_identity(
    db: AsyncSession, *, user: User, claims: GoogleClaims
) -> None:
    if claims.email != user.email:
        raise GoogleEmailMismatchError

    identity = await db.scalar(
        select(Identity).where(
            Identity.provider == GOOGLE_PROVIDER,
            Identity.provider_subject == claims.subject,
        )
    )
    if identity is not None:
        if identity.user_id != user.id:
            raise GoogleIdentityConflictError
        return

    own_google_identity = await db.scalar(
        select(Identity).where(
            Identity.user_id == user.id,
            Identity.provider == GOOGLE_PROVIDER,
        )
    )
    if own_google_identity is not None:
        raise GoogleIdentityConflictError

    db.add(
        Identity(
            user_id=user.id,
            provider=GOOGLE_PROVIDER,
            provider_subject=claims.subject,
            password_hash=None,
        )
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise GoogleIdentityConflictError from exc


async def has_google_identity(db: AsyncSession, *, user: User) -> bool:
    identity_id = await db.scalar(
        select(Identity.id).where(
            Identity.user_id == user.id,
            Identity.provider == GOOGLE_PROVIDER,
        )
    )
    return identity_id is not None
