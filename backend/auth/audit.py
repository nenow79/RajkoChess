from typing import Any

from db.models import AuditLog
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentAuth


async def write_audit(
    db: AsyncSession,
    *,
    current: CurrentAuth,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
    outcome: str = "success",
) -> AuditLog:
    entry = AuditLog(
        actor_user_id=current.user.id,
        actor_session_id=current.session.id,
        action=action[:80],
        resource_type=resource_type[:40],
        resource_id=resource_id[:80] if resource_id else None,
        outcome=outcome[:16],
        reason=reason.strip()[:1000] if reason else None,
        details=details or {},
    )
    db.add(entry)
    await db.flush()
    return entry
