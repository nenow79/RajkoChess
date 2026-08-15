import uuid
from datetime import datetime, timezone
from typing import Any

from db.models import Analysis, AnalysisStatus, Game, GameSource, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


def parse_game_source(metadata: dict[str, Any]) -> GameSource:
    raw_source = metadata.get("source")
    if raw_source is None:
        raw_source = "chesscom" if metadata.get("id") else "pgn"
    try:
        return GameSource(str(raw_source))
    except ValueError:
        return GameSource.PGN


def parse_played_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


async def persist_imported_game(
    db: AsyncSession,
    *,
    user: User,
    pgn: str,
    metadata: dict[str, Any],
) -> Game:
    source = parse_game_source(metadata)
    raw_external_id = metadata.get("id") if source == GameSource.CHESSCOM else None
    external_id = str(raw_external_id)[:128] if raw_external_id else None
    model = None
    if external_id:
        model = await db.scalar(
            select(Game).where(
                Game.owner_id == user.id,
                Game.source == source,
                Game.external_id == external_id,
            )
        )
    if model is None:
        model = Game(
            owner_id=user.id,
            source=source,
            external_id=external_id,
            pgn=pgn,
            metadata_json=metadata,
            played_at=parse_played_at(metadata.get("played_at")),
        )
        db.add(model)
    else:
        model.pgn = pgn
        model.metadata_json = metadata
        model.played_at = parse_played_at(metadata.get("played_at"))
    await db.flush()
    return model


async def record_completed_analysis(
    db: AsyncSession,
    *,
    user: User,
    game_id: uuid.UUID,
    engine_result: dict[str, Any],
    coach_response: str,
) -> Analysis:
    model = Analysis(
        owner_id=user.id,
        game_id=game_id,
        status=AnalysisStatus.COMPLETED,
        engine_result=engine_result,
        coach_response=coach_response,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(model)
    await db.flush()
    return model


async def list_owned_games(
    db: AsyncSession,
    *,
    user: User,
    limit: int,
    offset: int,
    source: GameSource | None = None,
) -> list[Game]:
    statement = select(Game).where(Game.owner_id == user.id)
    if source is not None:
        statement = statement.where(Game.source == source)
    models = await db.scalars(
        statement
        .order_by(Game.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(models)


async def get_owned_game(
    db: AsyncSession, *, user: User, game_id: uuid.UUID, with_analyses: bool = False
) -> Game | None:
    statement = select(Game).where(Game.id == game_id, Game.owner_id == user.id)
    if with_analyses:
        statement = statement.options(selectinload(Game.analyses))
    return await db.scalar(statement)


def game_response(model: Game, *, include_pgn: bool = False) -> dict[str, Any]:
    metadata = model.metadata_json
    response: dict[str, Any] = {
        "id": str(model.id),
        "source": model.source.value,
        "external_id": model.external_id,
        "played_at": model.played_at.isoformat() if model.played_at else None,
        "opponent": metadata.get("opponent") or metadata.get("bot_name"),
        "result": metadata.get("result"),
        "color": metadata.get("color"),
        "created_at": model.created_at.isoformat(),
    }
    if include_pgn:
        response.update({"pgn": model.pgn, "metadata": metadata})
    return response


def analysis_response(model: Analysis) -> dict[str, Any]:
    return {
        "id": str(model.id),
        "game_id": str(model.game_id),
        "status": model.status.value,
        "engine_result": model.engine_result,
        "coach_response": model.coach_response,
        "completed_at": model.completed_at.isoformat() if model.completed_at else None,
        "created_at": model.created_at.isoformat(),
    }
