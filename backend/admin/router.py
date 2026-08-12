import uuid
from datetime import datetime, timezone
from typing import Annotated

from auth.audit import write_audit
from auth.dependencies import CurrentAuth, require_admin, require_admin_write
from auth.policies import ENTITLEMENT_DEFINITIONS, all_effective_entitlements
from chess_logic.bot_catalog import bot_response
from db.models import AuditLog, AuthSession, Bot, Entitlement, User, UserStatus
from db.session import get_db_session
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from admin.schemas import (
    AdminBotInspect,
    AdminUserResponse,
    AdminUserUpdate,
    EntitlementUpdate,
)

router = APIRouter(prefix="/api/admin", tags=["Administration"])


def user_response(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status.value,
        system_role=user.system_role.value,
        email_verified=user.email_verified_at is not None,
        created_at=user.created_at.isoformat(),
    )


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    current: Annotated[CurrentAuth, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[AdminUserResponse]:
    users = (
        await db.scalars(
            select(User).order_by(User.created_at, User.id).offset(offset).limit(limit)
        )
    ).all()
    return [user_response(user) for user in users]


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    current: Annotated[CurrentAuth, Depends(require_admin_write)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminUserResponse:
    if user_id == current.user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nie można zmienić własnej roli ani statusu",
        )
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono użytkownika")

    before = {"system_role": target.system_role.value, "status": target.status.value}
    if payload.system_role is not None:
        target.system_role = payload.system_role
    if payload.status is not None:
        target.status = UserStatus(payload.status)
        if target.status == UserStatus.BLOCKED:
            await db.execute(
                update(AuthSession)
                .where(
                    AuthSession.user_id == target.id,
                    AuthSession.revoked_at.is_(None),
                )
                .values(
                    revoked_at=datetime.now(timezone.utc),
                    revoked_reason="account_blocked",
                )
            )

    after = {"system_role": target.system_role.value, "status": target.status.value}
    await write_audit(
        db,
        current=current,
        action="user.access_changed",
        resource_type="user",
        resource_id=str(target.id),
        reason=payload.reason,
        details={"before": before, "after": after},
    )
    await db.commit()
    await db.refresh(target)
    return user_response(target)


@router.get("/users/{user_id}/entitlements")
async def get_user_entitlements(
    user_id: uuid.UUID,
    current: Annotated[CurrentAuth, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono użytkownika")
    return {
        "user_id": str(target.id),
        "entitlements": await all_effective_entitlements(db, user=target),
    }


@router.put("/users/{user_id}/entitlements/{key}")
async def set_user_entitlement(
    user_id: uuid.UUID,
    key: str,
    payload: EntitlementUpdate,
    current: Annotated[CurrentAuth, Depends(require_admin_write)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    if key not in ENTITLEMENT_DEFINITIONS:
        raise HTTPException(status_code=400, detail="Nieznane uprawnienie produktowe")
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono użytkownika")

    model = await db.scalar(
        select(Entitlement).where(
            Entitlement.user_id == target.id, Entitlement.key == key
        )
    )
    before = None
    if model is None:
        model = Entitlement(user_id=target.id, key=key, enabled=payload.enabled)
        db.add(model)
    else:
        before = {"enabled": model.enabled, "limit": model.limit_value}
    model.enabled = payload.enabled
    model.limit_value = payload.limit_value
    model.source = "manual"
    await db.flush()
    await write_audit(
        db,
        current=current,
        action="entitlement.set",
        resource_type="entitlement",
        resource_id=f"{target.id}:{key}",
        reason=payload.reason,
        details={
            "before": before,
            "after": {"enabled": model.enabled, "limit": model.limit_value},
        },
    )
    await db.commit()
    return {
        "user_id": str(target.id),
        "key": key,
        "enabled": model.enabled,
        "limit": model.limit_value,
        "source": model.source,
    }


@router.post("/bots/{bot_id}/inspect")
async def inspect_private_bot(
    bot_id: uuid.UUID,
    payload: AdminBotInspect,
    current: Annotated[CurrentAuth, Depends(require_admin_write)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    bot = await db.get(Bot, bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono bota")
    await write_audit(
        db,
        current=current,
        action="bot.admin_inspected",
        resource_type="bot",
        resource_id=str(bot.id),
        reason=payload.reason,
        details={
            "owner_id": str(bot.owner_id) if bot.owner_id else None,
            "visibility": bot.visibility.value,
        },
    )
    await db.commit()
    return bot_response(bot, current.user)


@router.get("/audit-log")
async def list_audit_log(
    current: Annotated[CurrentAuth, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    resource_type: str | None = None,
    action: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    statement = select(AuditLog)
    if resource_type:
        statement = statement.where(AuditLog.resource_type == resource_type)
    if action:
        statement = statement.where(AuditLog.action == action)
    entries = (
        await db.scalars(
            statement.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return {
        "entries": [
            {
                "id": str(entry.id),
                "actor_user_id": str(entry.actor_user_id)
                if entry.actor_user_id
                else None,
                "actor_session_id": str(entry.actor_session_id)
                if entry.actor_session_id
                else None,
                "action": entry.action,
                "resource_type": entry.resource_type,
                "resource_id": entry.resource_id,
                "outcome": entry.outcome,
                "reason": entry.reason,
                "details": entry.details,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in entries
        ]
    }
