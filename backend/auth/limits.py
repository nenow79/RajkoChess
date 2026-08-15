from contextlib import asynccontextmanager
from typing import AsyncIterator

from db.models import Bot, BotVisibility, User
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.plans import (
    PLAN_DEFINITIONS,
    effective_plan,
    ensure_monthly_quota,
    record_usage,
)
from auth.roles import is_admin
from rate_limit import concurrency_slot, enforce_rate_limit, global_concurrency_slot
from settings import get_settings


OPERATIONAL_LIMITS = {
    "stockfish_position": {
        "free": (30, 300),
        "premium": (120, 300),
        "admin": (300, 300),
    },
    "ai_game_review": {
        "free": (5, 3600),
        "premium": (20, 3600),
        "admin": (50, 3600),
    },
    "ai_chat": {
        "free": (10, 3600),
        "premium": (40, 3600),
        "admin": (100, 3600),
    },
    "ai_bot_draft": {
        "free": (5, 3600),
        "premium": (20, 3600),
        "admin": (50, 3600),
    },
    "bot_move": {
        "free": (120, 300),
        "premium": (240, 300),
        "admin": (300, 300),
    },
    "chesscom_import": {
        "free": (12, 300),
        "premium": (30, 300),
        "admin": (60, 300),
    },
}


def global_concurrency_limit(group: str) -> int:
    settings = get_settings()
    limits = {
        "engine": settings.global_engine_concurrency,
        "full_analysis": settings.global_full_analysis_concurrency,
        "llm": settings.global_llm_concurrency,
        "external_api": settings.global_external_api_concurrency,
    }
    try:
        return limits[group]
    except KeyError as exc:
        raise ValueError(f"Nieznana globalna grupa współbieżności: {group}") from exc


@asynccontextmanager
async def limited_operation(
    db: AsyncSession,
    *,
    user: User,
    operation: str,
    monthly_key: str | None = None,
    concurrency_group: str,
    lock_ttl_seconds: int = 300,
) -> AsyncIterator[None]:
    plan = await effective_plan(db, user=user)
    rate_plan = "admin" if is_admin(user) else plan.key
    try:
        rate_limit, window = OPERATIONAL_LIMITS[operation][rate_plan]
    except KeyError as exc:
        raise ValueError(f"Nieznana operacja limitowana: {operation}") from exc

    await enforce_rate_limit(
        bucket=f"operation:{operation}",
        identity=str(user.id),
        limit=rate_limit,
        window_seconds=window,
    )

    if monthly_key is not None:
        used, monthly_limit = await ensure_monthly_quota(
            db, user=user, key=monthly_key
        )
        if monthly_limit is not None and used >= monthly_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Wykorzystano miesięczny limit {monthly_limit} operacji. "
                    "Limit odnowi się pierwszego dnia następnego miesiąca."
                ),
            )

    async with concurrency_slot(
        bucket=concurrency_group,
        identity=str(user.id),
        ttl_seconds=lock_ttl_seconds,
    ):
        async with global_concurrency_slot(
            bucket=concurrency_group,
            limit=global_concurrency_limit(concurrency_group),
            ttl_seconds=lock_ttl_seconds,
        ):
            yield

    if monthly_key is not None:
        await record_usage(db, user=user, key=monthly_key)


async def ensure_custom_bot_capacity(db: AsyncSession, *, user: User) -> None:
    if is_admin(user):
        return
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    plan = await effective_plan(db, user=user)
    limit = PLAN_DEFINITIONS[plan.key].resource_limits["custom_bots"]
    count = await db.scalar(
        select(func.count(Bot.id)).where(
            Bot.owner_id == user.id,
            Bot.visibility == BotVisibility.PRIVATE,
        )
    )
    if int(count or 0) >= limit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Plan {plan.key.title()} pozwala mieć maksymalnie {limit} "
                "prywatnych botów."
            ),
        )


async def ensure_monthly_available(
    db: AsyncSession, *, user: User, key: str
) -> None:
    used, limit = await ensure_monthly_quota(db, user=user, key=key)
    if limit is not None and used >= limit:
        if limit == 0:
            detail = "Ta funkcja jest dostępna w planie Premium."
        else:
            detail = (
                f"Wykorzystano miesięczny limit {limit} operacji. "
                "Limit odnowi się pierwszego dnia następnego miesiąca."
            )
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
