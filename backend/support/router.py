import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from auth.audit import write_audit
from auth.dependencies import (
    CurrentAuth,
    get_current_auth,
    require_admin,
    require_admin_write,
    require_csrf,
)
from db.models import (
    Announcement,
    AnnouncementRead,
    SupportMessage,
    SupportTicket,
    SystemRole,
    User,
    UserStatus,
)
from db.session import get_db_session
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from rate_limit import enforce_rate_limit, request_ip
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from support.schemas import (
    AdminTicketCreate,
    AnnouncementCreate,
    TicketCreate,
    TicketMessageCreate,
    TicketRead,
    TicketStatusUpdate,
)

router = APIRouter(prefix="/api/support", tags=["Support"])
admin_router = APIRouter(prefix="/api/admin/support", tags=["Administration"])


def message_response(message: SupportMessage) -> dict:
    return {
        "id": str(message.id),
        "author_role": message.author_role,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
    }


async def announcement_response(
    db: AsyncSession, *, announcement: Announcement, user: User | None = None
) -> dict:
    read = False
    replied_ticket_id = None
    if user is not None:
        read = (
            await db.scalar(
                select(AnnouncementRead.announcement_id).where(
                    AnnouncementRead.announcement_id == announcement.id,
                    AnnouncementRead.user_id == user.id,
                )
            )
            is not None
        )
        replied_ticket_id = await db.scalar(
            select(SupportTicket.id).where(
                SupportTicket.owner_id == user.id,
                SupportTicket.source_announcement_id == announcement.id,
            )
        )
    response = {
        "id": str(announcement.id),
        "title": announcement.title,
        "content": announcement.content,
        "published_at": announcement.published_at.isoformat(),
        "expires_at": announcement.expires_at.isoformat()
        if announcement.expires_at
        else None,
        "archived_at": announcement.archived_at.isoformat()
        if announcement.archived_at
        else None,
    }
    if user is not None:
        response.update(
            {
                "read": read,
                "replied_ticket_id": str(replied_ticket_id)
                if replied_ticket_id
                else None,
            }
        )
    return response


def visible_announcement_conditions(user: User, now: datetime) -> list:
    return [
        Announcement.published_at <= now,
        Announcement.published_at >= user.created_at,
        Announcement.archived_at.is_(None),
        or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
    ]


async def unread_for_ticket(
    db: AsyncSession,
    *,
    ticket: SupportTicket,
    recipient: Literal["user", "admin"],
) -> int:
    if recipient == "user":
        author_role = "admin"
        last_read = ticket.user_last_read_at
    else:
        author_role = "user"
        last_read = ticket.admin_last_read_at
    conditions = [
        SupportMessage.ticket_id == ticket.id,
        SupportMessage.author_role == author_role,
    ]
    if last_read is not None:
        conditions.append(SupportMessage.created_at > last_read)
    return int(
        await db.scalar(select(func.count(SupportMessage.id)).where(*conditions)) or 0
    )


async def ticket_response(
    db: AsyncSession,
    *,
    ticket: SupportTicket,
    recipient: Literal["user", "admin"],
    owner: User | None = None,
    include_messages: bool = False,
) -> dict:
    last_message_at = await db.scalar(
        select(func.max(SupportMessage.created_at)).where(
            SupportMessage.ticket_id == ticket.id
        )
    )
    response = {
        "id": str(ticket.id),
        "category": ticket.category,
        "subject": ticket.subject,
        "status": ticket.status,
        "initiated_by": ticket.initiated_by,
        "source_announcement_id": str(ticket.source_announcement_id)
        if ticket.source_announcement_id
        else None,
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat(),
        "last_message_at": last_message_at.isoformat() if last_message_at else None,
        "unread_count": await unread_for_ticket(
            db, ticket=ticket, recipient=recipient
        ),
    }
    if owner is not None:
        response["owner"] = {
            "id": str(owner.id),
            "email": owner.email,
            "display_name": owner.display_name,
        }
    if include_messages:
        messages = (
            await db.scalars(
                select(SupportMessage)
                .where(SupportMessage.ticket_id == ticket.id)
                .order_by(SupportMessage.created_at, SupportMessage.id)
            )
        ).all()
        response["messages"] = [message_response(message) for message in messages]
    return response


async def owned_ticket(
    db: AsyncSession, *, ticket_id: uuid.UUID, owner_id: uuid.UUID
) -> SupportTicket:
    ticket = await db.scalar(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id, SupportTicket.owner_id == owner_id
        )
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono zgłoszenia")
    return ticket


async def any_ticket(db: AsyncSession, *, ticket_id: uuid.UUID) -> SupportTicket:
    ticket = await db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono zgłoszenia")
    return ticket


async def total_unread(
    db: AsyncSession,
    *,
    recipient: Literal["user", "admin"],
    owner_id: uuid.UUID | None = None,
) -> int:
    query = select(func.count(SupportMessage.id)).join(
        SupportTicket, SupportTicket.id == SupportMessage.ticket_id
    )
    if recipient == "user":
        query = query.where(
            SupportTicket.owner_id == owner_id,
            SupportMessage.author_role == "admin",
            or_(
                SupportTicket.user_last_read_at.is_(None),
                SupportMessage.created_at > SupportTicket.user_last_read_at,
            ),
        )
    else:
        query = query.where(
            SupportMessage.author_role == "user",
            or_(
                SupportTicket.admin_last_read_at.is_(None),
                SupportMessage.created_at > SupportTicket.admin_last_read_at,
            ),
        )
    ticket_count = int(await db.scalar(query) or 0)
    if recipient != "user" or owner_id is None:
        return ticket_count

    user = await db.get(User, owner_id)
    if user is None:
        return ticket_count
    now = datetime.now(timezone.utc)
    announcement_count = int(
        await db.scalar(
            select(func.count(Announcement.id))
            .outerjoin(
                AnnouncementRead,
                (AnnouncementRead.announcement_id == Announcement.id)
                & (AnnouncementRead.user_id == owner_id),
            )
            .where(
                *visible_announcement_conditions(user, now),
                AnnouncementRead.announcement_id.is_(None),
            )
        )
        or 0
    )
    return ticket_count + announcement_count


async def mark_read(
    db: AsyncSession,
    *,
    ticket: SupportTicket,
    recipient: Literal["user", "admin"],
    through_message_id: uuid.UUID,
) -> None:
    through_message = await db.scalar(
        select(SupportMessage).where(
            SupportMessage.ticket_id == ticket.id,
            SupportMessage.id == through_message_id,
        )
    )
    if through_message is None:
        raise HTTPException(status_code=400, detail="Nieprawidłowy zakres odczytu")
    field = (
        SupportTicket.user_last_read_at
        if recipient == "user"
        else SupportTicket.admin_last_read_at
    )
    # Preserve updated_at: reading a ticket must not move it to the top of the inbox.
    await db.execute(
        update(SupportTicket)
        .where(SupportTicket.id == ticket.id)
        .values(
            {
                field: case(
                    (
                        or_(field.is_(None), field < through_message.created_at),
                        through_message.created_at,
                    ),
                    else_=field,
                ),
                SupportTicket.updated_at: SupportTicket.updated_at,
            }
        )
    )


@router.get("/unread-count")
async def my_unread_count(
    current: Annotated[CurrentAuth, Depends(get_current_auth)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    return {
        "unread_count": await total_unread(
            db, recipient="user", owner_id=current.user.id
        )
    }


@router.get("/tickets")
async def list_my_tickets(
    current: Annotated[CurrentAuth, Depends(get_current_auth)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=50, ge=1, le=100),
):
    tickets = (
        await db.scalars(
            select(SupportTicket)
            .where(SupportTicket.owner_id == current.user.id)
            .order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc())
            .limit(limit)
        )
    ).all()
    return {
        "tickets": [
            await ticket_response(db, ticket=ticket, recipient="user")
            for ticket in tickets
        ]
    }


@router.post("/tickets", status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreate,
    request: Request,
    current: Annotated[CurrentAuth, Depends(require_csrf)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    await enforce_rate_limit(
        bucket="support-ticket-create",
        identity=f"{current.user.id}:{request_ip(request)}",
        limit=10,
        window_seconds=86_400,
    )
    now = datetime.now(timezone.utc)
    ticket = SupportTicket(
        owner_id=current.user.id,
        category=payload.category,
        subject=payload.subject,
        status="open",
        initiated_by="user",
        user_last_read_at=now,
    )
    db.add(ticket)
    await db.flush()
    db.add(
        SupportMessage(
            ticket_id=ticket.id,
            author_id=current.user.id,
            author_role="user",
            content=payload.message,
        )
    )
    await db.commit()
    await db.refresh(ticket)
    return await ticket_response(
        db, ticket=ticket, recipient="user", include_messages=True
    )


@router.get("/tickets/{ticket_id}")
async def get_my_ticket(
    ticket_id: uuid.UUID,
    current: Annotated[CurrentAuth, Depends(get_current_auth)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    ticket = await owned_ticket(db, ticket_id=ticket_id, owner_id=current.user.id)
    return await ticket_response(
        db, ticket=ticket, recipient="user", include_messages=True
    )


@router.post("/tickets/{ticket_id}/messages")
async def reply_to_my_ticket(
    ticket_id: uuid.UUID,
    payload: TicketMessageCreate,
    request: Request,
    current: Annotated[CurrentAuth, Depends(require_csrf)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    await enforce_rate_limit(
        bucket="support-message-create",
        identity=f"{current.user.id}:{request_ip(request)}",
        limit=30,
        window_seconds=3_600,
    )
    ticket = await owned_ticket(db, ticket_id=ticket_id, owner_id=current.user.id)
    now = datetime.now(timezone.utc)
    db.add(
        SupportMessage(
            ticket_id=ticket.id,
            author_id=current.user.id,
            author_role="user",
            content=payload.message,
        )
    )
    ticket.status = "open"
    ticket.closed_at = None
    ticket.updated_at = now
    ticket.user_last_read_at = now
    await db.commit()
    await db.refresh(ticket)
    return await ticket_response(
        db, ticket=ticket, recipient="user", include_messages=True
    )


@router.post("/tickets/{ticket_id}/read")
async def mark_my_ticket_read(
    ticket_id: uuid.UUID,
    payload: TicketRead,
    current: Annotated[CurrentAuth, Depends(require_csrf)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    ticket = await owned_ticket(db, ticket_id=ticket_id, owner_id=current.user.id)
    await mark_read(
        db,
        ticket=ticket,
        recipient="user",
        through_message_id=payload.through_message_id,
    )
    await db.commit()
    return {
        "unread_count": await total_unread(
            db, recipient="user", owner_id=current.user.id
        )
    }


@router.get("/announcements")
async def list_my_announcements(
    current: Annotated[CurrentAuth, Depends(get_current_auth)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=30, ge=1, le=100),
):
    now = datetime.now(timezone.utc)
    announcements = (
        await db.scalars(
            select(Announcement)
            .where(*visible_announcement_conditions(current.user, now))
            .order_by(Announcement.published_at.desc(), Announcement.id.desc())
            .limit(limit)
        )
    ).all()
    return {
        "announcements": [
            await announcement_response(db, announcement=item, user=current.user)
            for item in announcements
        ]
    }


@router.post("/announcements/{announcement_id}/read")
async def mark_announcement_read(
    announcement_id: uuid.UUID,
    current: Annotated[CurrentAuth, Depends(require_csrf)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    now = datetime.now(timezone.utc)
    announcement = await db.scalar(
        select(Announcement).where(
            Announcement.id == announcement_id,
            *visible_announcement_conditions(current.user, now),
        )
    )
    if announcement is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono ogłoszenia")
    existing = await db.get(AnnouncementRead, (announcement.id, current.user.id))
    if existing is None:
        db.add(
            AnnouncementRead(
                announcement_id=announcement.id,
                user_id=current.user.id,
                read_at=now,
            )
        )
        await db.commit()
    return {
        "unread_count": await total_unread(
            db, recipient="user", owner_id=current.user.id
        )
    }


@router.post("/announcements/{announcement_id}/reply")
async def reply_to_announcement(
    announcement_id: uuid.UUID,
    payload: TicketMessageCreate,
    request: Request,
    current: Annotated[CurrentAuth, Depends(require_csrf)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    await enforce_rate_limit(
        bucket="support-message-create",
        identity=f"{current.user.id}:{request_ip(request)}",
        limit=30,
        window_seconds=3_600,
    )
    now = datetime.now(timezone.utc)
    announcement = await db.scalar(
        select(Announcement).where(
            Announcement.id == announcement_id,
            *visible_announcement_conditions(current.user, now),
        )
    )
    if announcement is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono ogłoszenia")

    ticket = await db.scalar(
        select(SupportTicket).where(
            SupportTicket.owner_id == current.user.id,
            SupportTicket.source_announcement_id == announcement.id,
        )
    )
    if ticket is None:
        ticket = SupportTicket(
            owner_id=current.user.id,
            category="message",
            subject=f"Odpowiedź: {announcement.title}"[:160],
            status="open",
            initiated_by="admin",
            source_announcement_id=announcement.id,
            user_last_read_at=now,
        )
        db.add(ticket)
        await db.flush()
        db.add(
            SupportMessage(
                ticket_id=ticket.id,
                author_id=announcement.created_by_user_id,
                author_role="admin",
                content=announcement.content,
            )
        )
    db.add(
        SupportMessage(
            ticket_id=ticket.id,
            author_id=current.user.id,
            author_role="user",
            content=payload.message,
        )
    )
    ticket.status = "open"
    ticket.closed_at = None
    ticket.updated_at = now
    ticket.user_last_read_at = now
    existing_read = await db.get(
        AnnouncementRead, (announcement.id, current.user.id)
    )
    if existing_read is None:
        db.add(
            AnnouncementRead(
                announcement_id=announcement.id,
                user_id=current.user.id,
                read_at=now,
            )
        )
    await db.commit()
    await db.refresh(ticket)
    return await ticket_response(
        db, ticket=ticket, recipient="user", include_messages=True
    )


@admin_router.get("/unread-count")
async def admin_unread_count(
    current: Annotated[CurrentAuth, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    return {"unread_count": await total_unread(db, recipient="admin")}


@admin_router.post("/tickets", status_code=status.HTTP_201_CREATED)
async def admin_create_ticket(
    payload: AdminTicketCreate,
    current: Annotated[CurrentAuth, Depends(require_admin_write)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    owner = await db.scalar(
        select(User).where(
            User.id == payload.user_id,
            User.status == UserStatus.ACTIVE,
            User.system_role == SystemRole.USER,
            User.email_verified_at.is_not(None),
        )
    )
    if owner is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono aktywnego użytkownika")
    now = datetime.now(timezone.utc)
    ticket = SupportTicket(
        owner_id=owner.id,
        category="message",
        subject=payload.subject,
        status="waiting_user",
        initiated_by="admin",
        admin_last_read_at=now,
    )
    db.add(ticket)
    await db.flush()
    message = SupportMessage(
        ticket_id=ticket.id,
        author_id=current.user.id,
        author_role="admin",
        content=payload.message,
    )
    db.add(message)
    await db.flush()
    await write_audit(
        db,
        current=current,
        action="support.admin_started_thread",
        resource_type="support_ticket",
        resource_id=str(ticket.id),
        details={"owner_id": str(owner.id), "message_id": str(message.id)},
    )
    await db.commit()
    await db.refresh(ticket)
    return await ticket_response(
        db, ticket=ticket, owner=owner, recipient="admin", include_messages=True
    )


@admin_router.get("/announcements")
async def list_admin_announcements(
    current: Annotated[CurrentAuth, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=30, ge=1, le=100),
):
    announcements = (
        await db.scalars(
            select(Announcement)
            .order_by(Announcement.published_at.desc(), Announcement.id.desc())
            .limit(limit)
        )
    ).all()
    items = []
    for announcement in announcements:
        response = await announcement_response(db, announcement=announcement)
        response["read_count"] = int(
            await db.scalar(
                select(func.count(AnnouncementRead.user_id)).where(
                    AnnouncementRead.announcement_id == announcement.id
                )
            )
            or 0
        )
        response["reply_count"] = int(
            await db.scalar(
                select(func.count(SupportTicket.id)).where(
                    SupportTicket.source_announcement_id == announcement.id
                )
            )
            or 0
        )
        items.append(response)
    return {"announcements": items}


@admin_router.post("/announcements", status_code=status.HTTP_201_CREATED)
async def create_announcement(
    payload: AnnouncementCreate,
    current: Annotated[CurrentAuth, Depends(require_admin_write)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    now = datetime.now(timezone.utc)
    recipient_count = int(
        await db.scalar(
            select(func.count(User.id)).where(
                User.status == UserStatus.ACTIVE,
                User.system_role == SystemRole.USER,
                User.email_verified_at.is_not(None),
                User.created_at <= now,
            )
        )
        or 0
    )
    announcement = Announcement(
        title=payload.title,
        content=payload.content,
        created_by_user_id=current.user.id,
        published_at=now,
        expires_at=payload.expires_at,
    )
    db.add(announcement)
    await db.flush()
    await write_audit(
        db,
        current=current,
        action="announcement.published",
        resource_type="announcement",
        resource_id=str(announcement.id),
        details={"recipient_count": recipient_count},
    )
    await db.commit()
    await db.refresh(announcement)
    response = await announcement_response(db, announcement=announcement)
    response.update({"recipient_count": recipient_count, "read_count": 0, "reply_count": 0})
    return response


@admin_router.post("/announcements/{announcement_id}/archive")
async def archive_announcement(
    announcement_id: uuid.UUID,
    current: Annotated[CurrentAuth, Depends(require_admin_write)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    announcement = await db.get(Announcement, announcement_id)
    if announcement is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono ogłoszenia")
    if announcement.archived_at is None:
        announcement.archived_at = datetime.now(timezone.utc)
        await write_audit(
            db,
            current=current,
            action="announcement.archived",
            resource_type="announcement",
            resource_id=str(announcement.id),
        )
        await db.commit()
        await db.refresh(announcement)
    return await announcement_response(db, announcement=announcement)


@admin_router.get("/tickets")
async def list_admin_tickets(
    current: Annotated[CurrentAuth, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=100, ge=1, le=200),
):
    rows = (
        await db.execute(
            select(SupportTicket, User)
            .join(User, User.id == SupportTicket.owner_id)
            .order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc())
            .limit(limit)
        )
    ).all()
    return {
        "tickets": [
            await ticket_response(
                db, ticket=ticket, owner=owner, recipient="admin"
            )
            for ticket, owner in rows
        ]
    }


@admin_router.get("/tickets/{ticket_id}")
async def get_admin_ticket(
    ticket_id: uuid.UUID,
    current: Annotated[CurrentAuth, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    ticket = await any_ticket(db, ticket_id=ticket_id)
    owner = await db.get(User, ticket.owner_id)
    return await ticket_response(
        db,
        ticket=ticket,
        owner=owner,
        recipient="admin",
        include_messages=True,
    )


@admin_router.post("/tickets/{ticket_id}/messages")
async def admin_reply_to_ticket(
    ticket_id: uuid.UUID,
    payload: TicketMessageCreate,
    current: Annotated[CurrentAuth, Depends(require_admin_write)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    ticket = await any_ticket(db, ticket_id=ticket_id)
    now = datetime.now(timezone.utc)
    message = SupportMessage(
        ticket_id=ticket.id,
        author_id=current.user.id,
        author_role="admin",
        content=payload.message,
    )
    db.add(message)
    ticket.status = "waiting_user"
    ticket.closed_at = None
    ticket.updated_at = now
    ticket.admin_last_read_at = now
    await db.flush()
    await write_audit(
        db,
        current=current,
        action="support.admin_replied",
        resource_type="support_ticket",
        resource_id=str(ticket.id),
        details={"message_id": str(message.id)},
    )
    await db.commit()
    await db.refresh(ticket)
    owner = await db.get(User, ticket.owner_id)
    return await ticket_response(
        db,
        ticket=ticket,
        owner=owner,
        recipient="admin",
        include_messages=True,
    )


@admin_router.post("/tickets/{ticket_id}/read")
async def mark_admin_ticket_read(
    ticket_id: uuid.UUID,
    payload: TicketRead,
    current: Annotated[CurrentAuth, Depends(require_admin_write)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    ticket = await any_ticket(db, ticket_id=ticket_id)
    await mark_read(
        db,
        ticket=ticket,
        recipient="admin",
        through_message_id=payload.through_message_id,
    )
    await db.commit()
    return {"unread_count": await total_unread(db, recipient="admin")}


@admin_router.patch("/tickets/{ticket_id}/status")
async def update_ticket_status(
    ticket_id: uuid.UUID,
    payload: TicketStatusUpdate,
    current: Annotated[CurrentAuth, Depends(require_admin_write)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    ticket = await any_ticket(db, ticket_id=ticket_id)
    previous = ticket.status
    now = datetime.now(timezone.utc)
    ticket.status = payload.status
    ticket.closed_at = now if payload.status == "closed" else None
    ticket.updated_at = now
    await write_audit(
        db,
        current=current,
        action="support.status_changed",
        resource_type="support_ticket",
        resource_id=str(ticket.id),
        details={"before": previous, "after": payload.status},
    )
    await db.commit()
    await db.refresh(ticket)
    owner = await db.get(User, ticket.owner_id)
    return await ticket_response(
        db,
        ticket=ticket,
        owner=owner,
        recipient="admin",
        include_messages=True,
    )
