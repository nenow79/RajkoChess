from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from db.models import PlanGrant, User, UsageEvent
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.roles import is_admin


@dataclass(frozen=True)
class PlanDefinition:
    key: Literal["free", "premium"]
    usage_limits: dict[str, int]
    resource_limits: dict[str, int]


PLAN_DEFINITIONS = {
    "free": PlanDefinition(
        key="free",
        usage_limits={
            "ai_game_review": 3,
            "ai_chat": 10,
            "ai_bot_draft": 1,
            "ai_bot_commentary": 0,
        },
        resource_limits={"custom_bots": 1},
    ),
    "premium": PlanDefinition(
        key="premium",
        usage_limits={
            "ai_game_review": 30,
            "ai_chat": 50,
            "ai_bot_draft": 10,
            "ai_bot_commentary": 100,
        },
        resource_limits={"custom_bots": 10},
    ),
}


@dataclass(frozen=True)
class EffectivePlan:
    key: Literal["free", "premium"]
    expires_at: datetime | None
    grant_id: str | None


def current_month_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return datetime(current.year, current.month, 1, tzinfo=timezone.utc)


async def effective_plan(
    db: AsyncSession, *, user: User, now: datetime | None = None
) -> EffectivePlan:
    current = now or datetime.now(timezone.utc)
    grant = await db.scalar(
        select(PlanGrant)
        .where(
            PlanGrant.user_id == user.id,
            PlanGrant.plan_key == "premium",
            PlanGrant.starts_at <= current,
            PlanGrant.ends_at > current,
            PlanGrant.revoked_at.is_(None),
        )
        .order_by(PlanGrant.ends_at.desc(), PlanGrant.created_at.desc())
        .limit(1)
    )
    if grant is None:
        return EffectivePlan(key="free", expires_at=None, grant_id=None)
    return EffectivePlan(
        key="premium", expires_at=grant.ends_at, grant_id=str(grant.id)
    )


async def usage_this_month(
    db: AsyncSession,
    *,
    user: User,
    key: str,
    plan_key: str,
    now: datetime | None = None,
) -> int:
    value = await db.scalar(
        select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
            UsageEvent.user_id == user.id,
            UsageEvent.key == key,
            UsageEvent.plan_key == plan_key,
            UsageEvent.occurred_at >= current_month_start(now),
        )
    )
    return int(value or 0)


async def plan_summary(
    db: AsyncSession, *, user: User, now: datetime | None = None
) -> dict:
    plan = await effective_plan(db, user=user, now=now)
    definition = PLAN_DEFINITIONS[plan.key]
    usage = {
        key: {
            "used": await usage_this_month(
                db, user=user, key=key, plan_key=plan.key, now=now
            ),
            "limit": limit,
        }
        for key, limit in definition.usage_limits.items()
    }
    if is_admin(user):
        usage = {
            key: {"used": item["used"], "limit": None}
            for key, item in usage.items()
        }
    return {
        "key": "admin" if is_admin(user) else plan.key,
        "base_plan": plan.key,
        "expires_at": plan.expires_at.isoformat() if plan.expires_at else None,
        "usage": usage,
        "resource_limits": {
            key: None if is_admin(user) else limit
            for key, limit in definition.resource_limits.items()
        },
    }


async def record_usage(
    db: AsyncSession, *, user: User, key: str, details: dict | None = None
) -> UsageEvent:
    plan = await effective_plan(db, user=user)
    event = UsageEvent(
        user_id=user.id,
        key=key,
        quantity=1,
        plan_key=plan.key,
        details=details or {},
    )
    db.add(event)
    await db.commit()
    return event


async def ensure_monthly_quota(
    db: AsyncSession, *, user: User, key: str
) -> tuple[int, int | None]:
    plan = await effective_plan(db, user=user)
    definition = PLAN_DEFINITIONS[plan.key]
    if key not in definition.usage_limits:
        raise ValueError(f"Nieznany licznik użycia: {key}")
    used = await usage_this_month(db, user=user, key=key, plan_key=plan.key)
    limit = None if is_admin(user) else definition.usage_limits[key]
    return used, limit
