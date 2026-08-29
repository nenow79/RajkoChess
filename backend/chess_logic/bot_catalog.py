import uuid
from collections.abc import Sequence

from auth.policies import owner_condition
from auth.roles import is_admin
from chess_logic.bots import BotStore
from chess_logic.openings import find_opening
from db.models import Bot, BotVisibility, User
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class BotNotFoundError(Exception):
    pass


class BotPermissionError(Exception):
    pass


def parse_bot_id(bot_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(bot_id)
    except (TypeError, ValueError) as exc:
        raise BotNotFoundError from exc


def parse_visibility(value: object, *, default: BotVisibility) -> BotVisibility:
    try:
        return BotVisibility(str(value or default.value))
    except ValueError as exc:
        raise ValueError("Nieprawidłowa widoczność bota") from exc


def visible_bot_filter(user: User):
    return or_(
        Bot.visibility == BotVisibility.PUBLIC, owner_condition(Bot.owner_id, user)
    )


def manageable_bot_filter(user: User):
    conditions = [
        and_(Bot.visibility == BotVisibility.PRIVATE, Bot.owner_id == user.id)
    ]
    if is_admin(user):
        conditions.append(Bot.visibility == BotVisibility.PUBLIC)
    return or_(*conditions)


def can_manage_bot(bot: Bot, user: User) -> bool:
    if bot.visibility == BotVisibility.PUBLIC:
        return is_admin(user)
    return bot.owner_id == user.id


def bot_response(bot: Bot, user: User) -> dict:
    openings = [dict(item) for item in bot.openings]
    for entry in openings:
        opening = find_opening(entry.get("opening_id", ""))
        if opening:
            entry.update({"name": opening["name"], "eco": opening["eco"]})

    manageable = can_manage_bot(bot, user)
    return {
        "id": str(bot.id),
        "owner_id": str(bot.owner_id) if bot.owner_id else None,
        "visibility": bot.visibility.value,
        "name": bot.name,
        "description": bot.description,
        "avatar": bot.avatar,
        "target_elo": bot.target_elo,
        "extra_weakening": bot.extra_weakening,
        "style": bot.style,
        "openings": openings,
        "phrases": bot.phrases,
        "created_at": bot.created_at.isoformat(),
        "updated_at": bot.updated_at.isoformat(),
        "can_edit": manageable,
        "can_delete": manageable,
    }


async def list_visible_bots(db: AsyncSession, *, user: User) -> Sequence[Bot]:
    result = await db.scalars(
        select(Bot)
        .where(visible_bot_filter(user))
        .order_by(Bot.visibility.desc(), Bot.created_at, Bot.id)
    )
    return result.all()


async def get_visible_bot(db: AsyncSession, *, bot_id: str, user: User) -> Bot:
    model = await db.scalar(
        select(Bot).where(Bot.id == parse_bot_id(bot_id), visible_bot_filter(user))
    )
    if model is None:
        raise BotNotFoundError
    return model


async def create_bot(
    db: AsyncSession, *, profile: dict, visibility: BotVisibility, user: User
) -> Bot:
    if visibility == BotVisibility.PUBLIC and not is_admin(user):
        raise BotPermissionError

    clean = BotStore.validate(profile)
    model = Bot(
        owner_id=None if visibility == BotVisibility.PUBLIC else user.id,
        visibility=visibility,
        **clean,
    )
    db.add(model)
    await db.flush()
    return model


async def update_bot(
    db: AsyncSession, *, bot_id: str, profile: dict, user: User
) -> Bot:
    model = await db.scalar(
        select(Bot).where(Bot.id == parse_bot_id(bot_id), manageable_bot_filter(user))
    )
    if model is None:
        raise BotNotFoundError

    requested_visibility = parse_visibility(
        profile.get("visibility"), default=model.visibility
    )
    if requested_visibility != model.visibility:
        raise BotPermissionError

    clean = BotStore.validate(profile)
    for key, value in clean.items():
        setattr(model, key, value)
    await db.flush()
    return model


async def delete_bot(db: AsyncSession, *, bot_id: str, user: User) -> Bot:
    model = await db.scalar(
        select(Bot).where(Bot.id == parse_bot_id(bot_id), manageable_bot_filter(user))
    )
    if model is None:
        raise BotNotFoundError
    await db.delete(model)
    await db.flush()
    return model
