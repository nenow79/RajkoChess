from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from db.models import Entitlement, User
from db.session import get_db_session
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentAuth, get_current_auth, require_csrf
from auth.roles import is_admin


@dataclass(frozen=True)
class EntitlementDefinition:
    key: str
    default_enabled: bool
    default_limit: int | None = None


ENTITLEMENT_DEFINITIONS = {
    item.key: item
    for item in (
        EntitlementDefinition("basic_analysis", True),
        EntitlementDefinition("ai_game_review", True),
        EntitlementDefinition("custom_bot", True),
        EntitlementDefinition("training_plan", False),
        EntitlementDefinition("priority_analysis", False),
    )
}


def owner_condition(owner_column, user: User):
    return owner_column == user.id


async def effective_entitlement(
    db: AsyncSession, *, user: User, key: str
) -> tuple[bool, int | None, str]:
    definition = ENTITLEMENT_DEFINITIONS.get(key)
    if definition is None:
        raise ValueError(f"Nieznane uprawnienie produktowe: {key}")
    if is_admin(user):
        return True, None, "admin"

    override = await db.scalar(
        select(Entitlement).where(
            Entitlement.user_id == user.id, Entitlement.key == key
        )
    )
    if override is not None:
        return override.enabled, override.limit_value, override.source
    return definition.default_enabled, definition.default_limit, "default"


async def all_effective_entitlements(db: AsyncSession, *, user: User) -> dict:
    return {
        key: {"enabled": enabled, "limit": limit_value, "source": source}
        for key in ENTITLEMENT_DEFINITIONS
        for enabled, limit_value, source in [
            await effective_entitlement(db, user=user, key=key)
        ]
    }


def require_entitlement(key: str, *, write: bool = False) -> Callable:
    if key not in ENTITLEMENT_DEFINITIONS:
        raise ValueError(f"Nieznane uprawnienie produktowe: {key}")

    auth_dependency = require_csrf if write else get_current_auth

    async def dependency(
        current: Annotated[CurrentAuth, Depends(auth_dependency)],
        db: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> CurrentAuth:
        enabled, _, _ = await effective_entitlement(db, user=current.user, key=key)
        if not enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Brak uprawnienia produktowego: {key}",
            )
        return current

    return dependency
