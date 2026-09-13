from datetime import datetime, timezone

from db.models import SupportMessage, SupportTicket, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

WELCOME_KEY = "welcome-v1"
WELCOME_SUBJECT = "Witaj w Rajko Chess"
WELCOME_CONTENT = (
    "Cześć! Witaj w Rajko Chess. Zacznij od zaimportowania jednej ze swoich "
    "partii i uruchomienia pełnej analizy. Jeśli coś będzie niejasne albo "
    "będziesz mieć pomysł na ulepszenie aplikacji, odpowiedz bezpośrednio na "
    "tę wiadomość."
)


async def ensure_welcome_thread(db: AsyncSession, *, user: User) -> SupportTicket:
    existing = await db.scalar(
        select(SupportTicket).where(
            SupportTicket.owner_id == user.id,
            SupportTicket.welcome_key == WELCOME_KEY,
        )
    )
    if existing is not None:
        return existing

    now = datetime.now(timezone.utc)
    ticket = SupportTicket(
        owner_id=user.id,
        category="message",
        subject=WELCOME_SUBJECT,
        status="waiting_user",
        initiated_by="system",
        welcome_key=WELCOME_KEY,
        admin_last_read_at=now,
    )
    db.add(ticket)
    await db.flush()
    db.add(
        SupportMessage(
            ticket_id=ticket.id,
            author_id=None,
            author_role="admin",
            content=WELCOME_CONTENT,
        )
    )
    return ticket
