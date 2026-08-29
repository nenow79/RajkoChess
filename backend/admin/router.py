import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from auth.audit import write_audit
from auth.dependencies import CurrentAuth, require_admin, require_admin_write
from auth.plans import effective_plan, plan_summary
from auth.policies import ENTITLEMENT_DEFINITIONS, all_effective_entitlements
from chess_logic.bot_catalog import bot_response
from chess_logic.runtime_settings import (
    BOT_GLOBAL_ELO_OFFSET_KEY,
    get_bot_global_elo_offset,
)
from db.models import (
    AuditLog,
    AuthSession,
    Bot,
    Entitlement,
    PlanGrant,
    RuntimeSetting,
    User,
    UserStatus,
)
from db.session import get_db_session
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from admin.schemas import (
    AdminReason,
    AdminBotInspect,
    AdminUserResponse,
    AdminUserUpdate,
    BotStrengthSettingUpdate,
    EntitlementUpdate,
    PremiumGrantRequest,
)
from admin.statistics import beta_statistics

router = APIRouter(prefix="/api/admin", tags=["Administration"])


@router.get("/statistics")
async def get_statistics(
    current: Annotated[CurrentAuth, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    return await beta_statistics(db)


@router.get("/settings/bot-strength")
async def get_bot_strength_setting(
    current: Annotated[CurrentAuth, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    offset, source = await get_bot_global_elo_offset(db)
    return {
        "bot_global_elo_offset": offset,
        "source": source,
        "minimum": -600,
        "maximum": 300,
    }


@router.put("/settings/bot-strength")
async def set_bot_strength_setting(
    payload: BotStrengthSettingUpdate,
    current: Annotated[CurrentAuth, Depends(require_admin_write)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    before, before_source = await get_bot_global_elo_offset(db)
    setting = await db.get(RuntimeSetting, BOT_GLOBAL_ELO_OFFSET_KEY)
    if setting is None:
        setting = RuntimeSetting(
            key=BOT_GLOBAL_ELO_OFFSET_KEY,
            value={"offset": payload.bot_global_elo_offset},
            updated_by_user_id=current.user.id,
        )
        db.add(setting)
    else:
        setting.value = {"offset": payload.bot_global_elo_offset}
        setting.updated_by_user_id = current.user.id
    await db.flush()
    await write_audit(
        db,
        current=current,
        action="settings.bot_strength_changed",
        resource_type="runtime_setting",
        resource_id=BOT_GLOBAL_ELO_OFFSET_KEY,
        reason=payload.reason,
        details={
            "before": {"offset": before, "source": before_source},
            "after": {"offset": payload.bot_global_elo_offset},
        },
    )
    await db.commit()
    return {
        "bot_global_elo_offset": payload.bot_global_elo_offset,
        "source": "database",
        "minimum": -600,
        "maximum": 300,
    }


def user_response(
    user: User,
    *,
    plan_key: Literal["free", "premium"] = "free",
    premium_expires_at: datetime | None = None,
) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status.value,
        system_role=user.system_role.value,
        email_verified=user.email_verified_at is not None,
        created_at=user.created_at.isoformat(),
        plan_key=plan_key,
        premium_expires_at=premium_expires_at.isoformat()
        if premium_expires_at
        else None,
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
    responses = []
    for user in users:
        plan = await effective_plan(db, user=user)
        responses.append(
            user_response(
                user, plan_key=plan.key, premium_expires_at=plan.expires_at
            )
        )
    return responses


@router.get("/users/{user_id}/plan")
async def get_user_plan(
    user_id: uuid.UUID,
    current: Annotated[CurrentAuth, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono użytkownika")
    return {"user_id": str(target.id), **await plan_summary(db, user=target)}


@router.post("/users/{user_id}/premium")
async def grant_premium(
    user_id: uuid.UUID,
    payload: PremiumGrantRequest,
    current: Annotated[CurrentAuth, Depends(require_admin_write)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono użytkownika")

    now = datetime.now(timezone.utc)
    active = await effective_plan(db, user=target, now=now)
    starts_at = now
    if payload.days is not None:
        from datetime import timedelta

        base = active.expires_at if active.expires_at and active.expires_at > now else now
        ends_at = base + timedelta(days=payload.days)
    else:
        ends_at = payload.ends_at
        if ends_at is None:
            raise HTTPException(status_code=400, detail="Brak daty zakończenia")
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)
        if ends_at <= now:
            raise HTTPException(status_code=400, detail="Data zakończenia musi być przyszła")

    grant = PlanGrant(
        user_id=target.id,
        plan_key="premium",
        starts_at=starts_at,
        ends_at=ends_at,
        source="manual",
        granted_by_user_id=current.user.id,
        reason=payload.reason,
    )
    db.add(grant)
    await db.flush()
    await write_audit(
        db,
        current=current,
        action="plan.premium_granted",
        resource_type="plan_grant",
        resource_id=str(grant.id),
        reason=payload.reason,
        details={
            "user_id": str(target.id),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
    )
    await db.commit()
    return {"user_id": str(target.id), **await plan_summary(db, user=target)}


@router.delete("/users/{user_id}/premium")
async def revoke_premium(
    user_id: uuid.UUID,
    payload: AdminReason,
    current: Annotated[CurrentAuth, Depends(require_admin_write)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono użytkownika")
    now = datetime.now(timezone.utc)
    grants = (
        await db.scalars(
            select(PlanGrant).where(
                PlanGrant.user_id == target.id,
                PlanGrant.starts_at <= now,
                PlanGrant.ends_at > now,
                PlanGrant.revoked_at.is_(None),
            )
        )
    ).all()
    if not grants:
        raise HTTPException(status_code=409, detail="Użytkownik nie ma aktywnego Premium")
    for grant in grants:
        grant.revoked_at = now
    await write_audit(
        db,
        current=current,
        action="plan.premium_revoked",
        resource_type="user",
        resource_id=str(target.id),
        reason=payload.reason,
        details={"grant_ids": [str(grant.id) for grant in grants]},
    )
    await db.commit()
    return {"user_id": str(target.id), **await plan_summary(db, user=target)}


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
