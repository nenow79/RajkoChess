from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from db.models import Analysis, AuthSession, ChatMessage, Game, UsageEvent, User
from sqlalchemy import BigInteger, Date, Numeric, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def beta_statistics(db: AsyncSession) -> dict[str, Any]:
    """Return aggregate-only product statistics for the administration panel."""
    now = datetime.now(timezone.utc)
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)
    chart_start = now.date() - timedelta(days=13)
    chart_start_at = datetime.combine(chart_start, datetime.min.time(), timezone.utc)

    total_users = int(await db.scalar(select(func.count(User.id))) or 0)
    verified_users = int(
        await db.scalar(
            select(func.count(User.id)).where(User.email_verified_at.is_not(None))
        )
        or 0
    )
    new_7d = int(
        await db.scalar(select(func.count(User.id)).where(User.created_at >= since_7d))
        or 0
    )
    new_30d = int(
        await db.scalar(select(func.count(User.id)).where(User.created_at >= since_30d))
        or 0
    )
    active_7d = int(
        await db.scalar(
            select(func.count(distinct(AuthSession.user_id))).where(
                AuthSession.last_seen_at >= since_7d
            )
        )
        or 0
    )
    active_30d = int(
        await db.scalar(
            select(func.count(distinct(AuthSession.user_id))).where(
                AuthSession.last_seen_at >= since_30d
            )
        )
        or 0
    )

    total_games = int(await db.scalar(select(func.count(Game.id))) or 0)
    game_users = int(
        await db.scalar(select(func.count(distinct(Game.owner_id)))) or 0
    )
    analyzed_games = int(
        await db.scalar(select(func.count(distinct(Analysis.game_id)))) or 0
    )
    total_analyses = int(await db.scalar(select(func.count(Analysis.id))) or 0)
    total_chat_messages = int(
        await db.scalar(select(func.count(ChatMessage.id))) or 0
    )
    source_rows = (
        await db.execute(
            select(Game.source, func.count(Game.id))
            .group_by(Game.source)
            .order_by(Game.source)
        )
    ).all()

    usage_filter = UsageEvent.occurred_at >= since_30d
    ai_operations = int(
        await db.scalar(
            select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(usage_filter)
        )
        or 0
    )
    ai_users = int(
        await db.scalar(
            select(func.count(distinct(UsageEvent.user_id))).where(usage_filter)
        )
        or 0
    )
    total_tokens = int(
        await db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        cast(UsageEvent.details["total_tokens"].astext, BigInteger)
                    ),
                    0,
                )
            ).where(usage_filter)
        )
        or 0
    )
    openrouter_cost = float(
        await db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        cast(
                            UsageEvent.details["openrouter_cost_credits"].astext,
                            Numeric(18, 10),
                        )
                    ),
                    0,
                )
            ).where(usage_filter)
        )
        or 0
    )
    usage_rows = (
        await db.execute(
            select(
                UsageEvent.key,
                func.sum(UsageEvent.quantity),
                func.count(distinct(UsageEvent.user_id)),
            )
            .where(usage_filter)
            .group_by(UsageEvent.key)
            .order_by(func.sum(UsageEvent.quantity).desc())
        )
    ).all()

    async def daily_counts(timestamp_column, id_column) -> dict[date, int]:
        day = cast(timestamp_column, Date)
        rows = (
            await db.execute(
                select(day, func.count(id_column))
                .where(timestamp_column >= chart_start_at)
                .group_by(day)
                .order_by(day)
            )
        ).all()
        return {row[0]: int(row[1]) for row in rows}

    registrations_by_day = await daily_counts(User.created_at, User.id)
    games_by_day = await daily_counts(Game.created_at, Game.id)
    usage_by_day = await daily_counts(
        UsageEvent.occurred_at, UsageEvent.id
    )
    daily = []
    for offset in range(14):
        day = chart_start + timedelta(days=offset)
        daily.append(
            {
                "date": day.isoformat(),
                "registrations": registrations_by_day.get(day, 0),
                "games": games_by_day.get(day, 0),
                "ai_operations": usage_by_day.get(day, 0),
            }
        )

    return {
        "generated_at": now.isoformat(),
        "users": {
            "total": total_users,
            "verified": verified_users,
            "new_7d": new_7d,
            "new_30d": new_30d,
            "active_7d": active_7d,
            "active_30d": active_30d,
        },
        "games": {
            "total": total_games,
            "users": game_users,
            "analyzed": analyzed_games,
            "analysis_rate": round(analyzed_games / total_games * 100, 1)
            if total_games
            else 0.0,
            "analyses": total_analyses,
            "chat_messages": total_chat_messages,
            "by_source": [
                {"source": source.value, "count": int(count)}
                for source, count in source_rows
            ],
        },
        "ai": {
            "period_days": 30,
            "operations": ai_operations,
            "users": ai_users,
            "total_tokens": total_tokens,
            "openrouter_cost_credits": round(openrouter_cost, 6),
            "by_key": [
                {"key": key, "operations": int(count), "users": int(users)}
                for key, count, users in usage_rows
            ],
        },
        "daily": daily,
    }
