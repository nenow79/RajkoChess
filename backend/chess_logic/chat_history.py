from __future__ import annotations

import uuid
from collections.abc import Iterable

from db.models import ChatMessage, User
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


async def add_chat_messages(
    db: AsyncSession,
    *,
    user: User,
    game_id: uuid.UUID,
    messages: Iterable[tuple[str, str, str]],
    fen: str | None,
) -> list[ChatMessage]:
    models = [
        ChatMessage(
            owner_id=user.id,
            game_id=game_id,
            role=role,
            kind=kind,
            content=content,
            fen=fen,
            message_order=message_order,
        )
        for message_order, (role, kind, content) in enumerate(messages)
    ]
    db.add_all(models)
    await db.flush()
    return models


async def list_chat_messages(
    db: AsyncSession,
    *,
    user: User,
    game_id: uuid.UUID,
    limit: int = 200,
) -> list[ChatMessage]:
    models = await db.scalars(
        select(ChatMessage)
        .where(
            ChatMessage.owner_id == user.id,
            ChatMessage.game_id == game_id,
        )
        .order_by(
            ChatMessage.created_at.desc(),
            ChatMessage.message_order.desc(),
            ChatMessage.id.desc(),
        )
        .limit(limit)
    )
    return list(reversed(list(models)))


async def latest_translatable_analysis(
    db: AsyncSession, *, user: User, game_id: uuid.UUID
) -> ChatMessage | None:
    return await db.scalar(
        select(ChatMessage)
        .where(
            ChatMessage.owner_id == user.id,
            ChatMessage.game_id == game_id,
            ChatMessage.role == "assistant",
            ChatMessage.kind.in_(("position", "game_review")),
        )
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(1)
    )


async def clear_chat_messages(
    db: AsyncSession, *, user: User, game_id: uuid.UUID
) -> None:
    await db.execute(
        delete(ChatMessage).where(
            ChatMessage.owner_id == user.id,
            ChatMessage.game_id == game_id,
        )
    )


def chat_message_response(model: ChatMessage) -> dict[str, str | None]:
    return {
        "id": str(model.id),
        "role": model.role,
        "kind": model.kind,
        "content": model.content,
        "fen": model.fen,
        "created_at": model.created_at.isoformat(),
    }
