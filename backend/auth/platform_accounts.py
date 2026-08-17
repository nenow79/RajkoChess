from __future__ import annotations

import re

from db.models import ChessPlatformAccount, User
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

SUPPORTED_PROVIDERS = {"chesscom"}
CHESSCOM_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,50}$")


def normalize_platform_username(provider: str, username: str) -> tuple[str, str]:
    normalized_provider = provider.strip().lower()
    if normalized_provider not in SUPPORTED_PROVIDERS:
        raise ValueError("Nieobsługiwana platforma szachowa")

    cleaned_username = username.strip()
    if normalized_provider == "chesscom" and not CHESSCOM_USERNAME_PATTERN.fullmatch(
        cleaned_username
    ):
        raise ValueError(
            "Login Chess.com może zawierać tylko litery, cyfry, _ i -"
        )
    return cleaned_username, cleaned_username.casefold()


async def list_platform_accounts(
    db: AsyncSession, *, user: User
) -> list[ChessPlatformAccount]:
    models = await db.scalars(
        select(ChessPlatformAccount)
        .where(ChessPlatformAccount.user_id == user.id)
        .order_by(ChessPlatformAccount.provider.asc())
    )
    return list(models)


async def upsert_platform_account(
    db: AsyncSession, *, user: User, provider: str, username: str
) -> ChessPlatformAccount:
    cleaned_username, normalized_username = normalize_platform_username(
        provider, username
    )
    normalized_provider = provider.strip().lower()
    model = await db.scalar(
        select(ChessPlatformAccount).where(
            ChessPlatformAccount.user_id == user.id,
            ChessPlatformAccount.provider == normalized_provider,
        )
    )
    if model is None:
        model = ChessPlatformAccount(
            user_id=user.id,
            provider=normalized_provider,
            username=cleaned_username,
            normalized_username=normalized_username,
        )
        db.add(model)
    else:
        model.username = cleaned_username
        model.normalized_username = normalized_username
    await db.commit()
    await db.refresh(model)
    return model


async def delete_platform_account(
    db: AsyncSession, *, user: User, provider: str
) -> None:
    normalized_provider = provider.strip().lower()
    if normalized_provider not in SUPPORTED_PROVIDERS:
        raise ValueError("Nieobsługiwana platforma szachowa")
    await db.execute(
        delete(ChessPlatformAccount).where(
            ChessPlatformAccount.user_id == user.id,
            ChessPlatformAccount.provider == normalized_provider,
        )
    )
    await db.commit()


def platform_account_response(model: ChessPlatformAccount) -> dict[str, str]:
    return {
        "provider": model.provider,
        "username": model.username,
        "updated_at": model.updated_at.isoformat(),
    }
