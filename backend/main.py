# main.py
import asyncio
import json
import uuid

import httpx
from admin.router import router as admin_router
from auth.audit import write_audit
from auth.dependencies import CurrentAuth, get_current_auth, require_csrf
from auth.policies import require_entitlement
from auth.limits import (
    ensure_custom_bot_capacity,
    ensure_monthly_available,
    limited_operation,
)
from auth.plans import record_usage
from auth.router import router as auth_router
from chess_logic.bot_catalog import (
    BotNotFoundError,
    BotPermissionError,
    bot_response,
    get_visible_bot,
    list_visible_bots,
    parse_visibility,
)
from chess_logic.bot_catalog import (
    create_bot as create_catalog_bot,
)
from chess_logic.bot_catalog import (
    delete_bot as delete_catalog_bot,
)
from chess_logic.bot_catalog import (
    update_bot as update_catalog_bot,
)
from chess_logic.bot_game import BotGameManager
from chess_logic.bots import BotStore
from chess_logic.chesscom import get_recent_games
from chess_logic.engine import analyze_game, analyze_position
from chess_logic.game import ChessGame
from chess_logic.chat_history import (
    add_chat_messages,
    chat_message_response,
    clear_chat_messages,
    latest_translatable_analysis,
    list_chat_messages,
)
from chess_logic.history import (
    analysis_response,
    game_response,
    get_owned_game,
    get_owned_games_by_external_ids,
    games_with_analysis_activity,
    list_owned_games,
    persist_imported_game,
    record_completed_analysis,
)
from chess_logic.lichess import get_opening_explorer_data
from chess_logic.llm_agent import (
    FULL_GAME_ANALYSIS_MESSAGE,
    LLMServiceError,
    OUT_OF_SCOPE_MESSAGE,
    generate_bot_profile,
    generate_chess_analysis,
    generate_game_analysis,
    get_default_model,
    is_chess_request,
    is_full_game_analysis_request,
    translate_analysis_to_english,
)
from chess_logic.openings import (
    find_opening,
    identify_opening,
    resolve_opening,
    search_openings,
)
from chess_logic.runtime_settings import get_bot_global_elo_offset
from db.models import BotVisibility, GameSource
from db.session import database_healthcheck, get_db_session
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Path, Request, status
from fastapi.middleware.cors import CORSMiddleware  # Dodany import
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from rate_limit import enforce_rate_limit, redis_healthcheck, request_ip

# Ładowanie zmiennych środowiskowych z .env
load_dotenv()

app = FastAPI(title="Chess API")
app.include_router(auth_router)
app.include_router(admin_router)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ImportGameRequest(BaseModel):
    pgn: str = Field(min_length=1, max_length=200_000)
    metadata: dict | None = None

    @field_validator("metadata")
    @classmethod
    def validate_metadata_size(cls, value: dict | None) -> dict | None:
        if value is not None and len(json.dumps(value, ensure_ascii=False)) > 10_000:
            raise ValueError("Metadane importu są zbyt duże")
        return value


class ImportPositionRequest(BaseModel):
    fen: str = Field(min_length=1, max_length=128)


class GamePositionRequest(BaseModel):
    ply: int


class BotStartRequest(BaseModel):
    bot_id: str = Field(min_length=1, max_length=64)
    player_color: str = "random"
    llm_commentary: bool = False


class BotMoveRequest(BaseModel):
    uci: str = Field(min_length=4, max_length=5)


class BotDraftRequest(BaseModel):
    description: str = Field(min_length=1, max_length=1000)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Porty Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stan gry jest tymczasowo trzymany osobno dla każdej uwierzytelnionej sesji.
games: dict[str, ChessGame] = {}
active_analysis_tasks: dict[str, asyncio.Task] = {}
last_ai_analyses: dict[str, str] = {}
bot_games = BotGameManager()


@app.get("/api/health", include_in_schema=False, response_model=None)
async def healthcheck() -> dict[str, str] | JSONResponse:
    database_ok, redis_ok = await asyncio.gather(
        database_healthcheck(), redis_healthcheck()
    )
    content = {
        "status": "ok" if database_ok and redis_ok else "unavailable",
        "postgres": "ok" if database_ok else "down",
        "redis": "ok" if redis_ok else "down",
    }
    if not database_ok or not redis_ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=content,
        )
    return content


def get_session_id(current: CurrentAuth = Depends(get_current_auth)) -> str:
    """Zwraca niepodrabialny klucz stanu z sesji zweryfikowanej w PostgreSQL."""
    return str(current.session.id)


def get_game(session_id: str = Depends(get_session_id)) -> ChessGame:
    if session_id not in games:
        games[session_id] = ChessGame()
    return games[session_id]


async def current_owned_game_id(
    db: AsyncSession, *, game: ChessGame, current: CurrentAuth
) -> uuid.UUID | None:
    imported = game.get_imported_game()
    raw_game_id = imported.get("game_id") if imported else None
    if not isinstance(raw_game_id, str):
        return None
    try:
        game_id = uuid.UUID(raw_game_id)
    except ValueError:
        return None
    stored = await get_owned_game(db, user=current.user, game_id=game_id)
    return stored.id if stored else None


@app.get("/api/bots")
async def list_bots(
    current: CurrentAuth = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db_session),
):
    models = await list_visible_bots(db, user=current.user)
    return {"bots": [bot_response(model, current.user) for model in models]}


@app.post("/api/bots")
async def create_bot(
    profile: dict,
    current: CurrentAuth = Depends(require_entitlement("custom_bot", write=True)),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        await ensure_custom_bot_capacity(db, user=current.user)
        visibility = parse_visibility(
            profile.get("visibility"), default=BotVisibility.PRIVATE
        )
        model = await create_catalog_bot(
            db, profile=profile, visibility=visibility, user=current.user
        )
        await write_audit(
            db,
            current=current,
            action="bot.created",
            resource_type="bot",
            resource_id=str(model.id),
            details={"visibility": model.visibility.value},
        )
        await db.commit()
        await db.refresh(model)
        return bot_response(model, current.user)
    except BotPermissionError:
        raise HTTPException(
            status_code=403, detail="Tylko administrator może tworzyć boty publiczne"
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/api/bots/{bot_id}")
async def update_bot(
    bot_id: str,
    profile: dict,
    current: CurrentAuth = Depends(require_csrf),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        model = await update_catalog_bot(
            db, bot_id=bot_id, profile=profile, user=current.user
        )
        await write_audit(
            db,
            current=current,
            action="bot.updated",
            resource_type="bot",
            resource_id=str(model.id),
            details={"visibility": model.visibility.value},
        )
        await db.commit()
        await db.refresh(model)
        return bot_response(model, current.user)
    except BotPermissionError:
        raise HTTPException(
            status_code=403, detail="Nie można zmienić widoczności istniejącego bota"
        )
    except BotNotFoundError:
        raise HTTPException(
            status_code=404, detail="Nie znaleziono bota lub nie masz uprawnień"
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/api/bots/{bot_id}")
async def delete_bot(
    bot_id: str,
    current: CurrentAuth = Depends(require_csrf),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        model = await delete_catalog_bot(db, bot_id=bot_id, user=current.user)
        await write_audit(
            db,
            current=current,
            action="bot.deleted",
            resource_type="bot",
            resource_id=str(model.id),
            details={"visibility": model.visibility.value},
        )
        await db.commit()
    except BotNotFoundError:
        raise HTTPException(
            status_code=404, detail="Nie znaleziono bota lub nie masz uprawnień"
        )
    return {"deleted": True}


@app.get("/api/openings")
async def opening_search(q: str = "", limit: int = 30):
    return {"openings": search_openings(q, min(max(limit, 1), 100))}


@app.post("/api/bots/draft")
async def draft_bot(
    request: BotDraftRequest,
    current: CurrentAuth = Depends(require_csrf),
    db: AsyncSession = Depends(get_db_session),
):
    if not request.description.strip():
        raise HTTPException(status_code=400, detail="Opisz charakter bota")
    try:
        async with limited_operation(
            db,
            user=current.user,
            operation="ai_bot_draft",
            monthly_key="ai_bot_draft",
            concurrency_group="llm",
        ):
            draft = await generate_bot_profile(request.description)
        warnings = []
        openings = []
        for color, queries in (draft.pop("opening_queries", {}) or {}).items():
            if color not in ("white", "black"):
                continue
            for query in queries[:3]:
                matched = resolve_opening(str(query))
                if matched:
                    openings.append(
                        {"opening_id": matched["id"], "color": color, "weight": 100}
                    )
                else:
                    warnings.append(f"Nie rozpoznano otwarcia: {query}")
        draft["openings"] = openings
        clean = BotStore.validate(draft)
        for entry in clean["openings"]:
            opening = find_opening(entry["opening_id"])
            if opening:
                entry.update({"name": opening["name"], "eco": opening["eco"]})
        return {"draft": clean, "warnings": warnings}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - normalize external provider failures
        raise HTTPException(
            status_code=502, detail=f"Nie udało się utworzyć profilu: {exc}"
        )


@app.post("/api/bot-games/start")
async def start_bot_game(
    request: BotStartRequest,
    session_id: str = Depends(get_session_id),
    current: CurrentAuth = Depends(require_csrf),
    db: AsyncSession = Depends(get_db_session),
):
    if request.player_color not in ("white", "black", "random"):
        raise HTTPException(status_code=400, detail="Nieprawidłowy kolor")
    if request.llm_commentary:
        await ensure_monthly_available(
            db, user=current.user, key="ai_bot_commentary"
        )
    try:
        model = await get_visible_bot(db, bot_id=request.bot_id, user=current.user)
        bot = bot_response(model, current.user)
        elo_offset, _ = await get_bot_global_elo_offset(db)
    except BotNotFoundError:
        raise HTTPException(status_code=404, detail="Nie znaleziono bota")
    try:
        async with limited_operation(
            db,
            user=current.user,
            operation="bot_move",
            concurrency_group="engine",
            lock_ttl_seconds=60,
        ):
            async with bot_games.lock(session_id):
                response = await bot_games.start(
                    session_id,
                    bot,
                    request.player_color,
                    llm_commentary=request.llm_commentary,
                    elo_offset=elo_offset,
                )
                commentary_usage = bot_games.take_commentary_usage(session_id)
        if response.get("llm_commentary"):
            await record_usage(
                db,
                user=current.user,
                key="ai_bot_commentary",
                details=commentary_usage,
            )
        return response
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/bot-games/current")
async def current_bot_game(session_id: str = Depends(get_session_id)):
    game = bot_games.games.get(session_id)
    return game.response() if game else {"status": "none"}


@app.post("/api/bot-games/move")
async def bot_game_move(
    request: BotMoveRequest,
    session_id: str = Depends(get_session_id),
    current: CurrentAuth = Depends(require_csrf),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        game = bot_games.games.get(session_id)
        if game and game.llm_commentary_enabled:
            try:
                await ensure_monthly_available(
                    db, user=current.user, key="ai_bot_commentary"
                )
            except HTTPException as exc:
                if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
                    raise
                # Wyczerpanie dodatku nie może zablokować trwającej partii.
                game.llm_commentary_enabled = False
        async with limited_operation(
            db,
            user=current.user,
            operation="bot_move",
            concurrency_group="engine",
            lock_ttl_seconds=60,
        ):
            async with bot_games.lock(session_id):
                response = await bot_games.move(session_id, request.uci)
                commentary_usage = bot_games.take_commentary_usage(session_id)
        if response.get("llm_commentary"):
            await record_usage(
                db,
                user=current.user,
                key="ai_bot_commentary",
                details=commentary_usage,
            )
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/bot-games/resign")
async def resign_bot_game(
    session_id: str = Depends(get_session_id),
    current: CurrentAuth = Depends(require_csrf),
):
    try:
        return bot_games.resign(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/bot-games/draw-offer")
async def bot_game_draw(
    session_id: str = Depends(get_session_id),
    current: CurrentAuth = Depends(require_csrf),
):
    try:
        return bot_games.draw_offer(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/bot-games/to-analysis")
async def bot_game_to_analysis(
    session_id: str = Depends(get_session_id),
    game: ChessGame = Depends(get_game),
    current: CurrentAuth = Depends(require_csrf),
):
    bot_game = bot_games.games.get(session_id)
    if not bot_game or bot_game.status == "active":
        raise HTTPException(status_code=400, detail="Najpierw zakończ partię")
    metadata = {
        "opponent": bot_game.bot["name"],
        "result": bot_game.result,
        "source": "bot",
    }
    return game.load_pgn(bot_game.pgn(), metadata)


class MoveRequest(BaseModel):
    uci: str  # np. "e2e4", "g1f3"
    preserve_imported_context: bool = False


class UndoRequest(BaseModel):
    preserve_imported_context: bool = False


@app.get("/api/position")
async def get_position(game: ChessGame = Depends(get_game)):
    """Zwraca pozycję i kontekst aktywnej partii z bieżącej sesji."""
    return game.get_position_state()


@app.post("/api/move")
async def make_move(
    request: MoveRequest,
    game: ChessGame = Depends(get_game),
    current: CurrentAuth = Depends(require_csrf),
):
    """Wykonuje ruch na szachownicy."""
    success = game.make_move(
        request.uci, preserve_imported_context=request.preserve_imported_context
    )
    if not success:
        raise HTTPException(status_code=400, detail="Nieprawidłowy lub nielegalny ruch")

    return {"fen": game.get_fen(), "history": game.get_history()}


@app.post("/api/undo")
async def undo_move(
    request: UndoRequest | None = None,
    game: ChessGame = Depends(get_game),
    current: CurrentAuth = Depends(require_csrf),
):
    """Cofa ostatni ruch na szachownicy."""
    preserve_imported_context = request.preserve_imported_context if request else False
    success = game.undo_move(preserve_imported_context=preserve_imported_context)
    if not success:
        raise HTTPException(status_code=400, detail="Brak ruchów do cofnięcia")

    return {"fen": game.get_fen(), "history": game.get_history()}


@app.get("/api/history")
async def get_history(game: ChessGame = Depends(get_game)):
    """Zwraca historię ruchów w obecnej partii."""
    return {"history": game.get_history()}


@app.get("/api/explorer")
async def get_explorer_stats(
    ratings: str | None = None,
    moves: int = 5,
    game: ChessGame = Depends(get_game),
):
    """
    Zwraca statystyki z bazy Lichess dla bieżącej pozycji na szachownicy.

    Opcjonalne filtry:
    - **ratings**: np. "1600,1800" (dostępne kubełki: 400, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2500)
    - **moves**: ilość zwracanych najpopularniejszych ruchów (domyślnie 5)
    """
    current_fen = game.get_fen()

    try:
        data = await get_opening_explorer_data(
            current_fen,
            max_moves=moves,
            ratings=ratings,
            fallback_opening=identify_opening(game.get_history()),
        )
        return data
    except httpx.HTTPStatusError as e:
        if e.response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            retry_after = e.response.headers.get("Retry-After", "30")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Lichess Explorer chwilowo ograniczył liczbę zapytań.",
                headers={"Retry-After": retry_after},
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Lichess Explorer jest chwilowo niedostępny.",
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Brak połączenia z Lichess API")


@app.get("/api/analyze")
async def analyze_current_position(
    time_limit: float = 0.5,
    lines: int = 3,
    game: ChessGame = Depends(get_game),
    current: CurrentAuth = Depends(require_entitlement("basic_analysis")),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Zwraca ocenę bieżącej pozycji ze Stockfisha.
    - **time_limit**: czas (w sekundach), jaki silnik ma na przemyślenie ruchu.
    - **lines**: ilość rozważanych najlepszych ruchów (MultiPV).
    """
    current_fen = game.get_fen()

    safe_time_limit = min(max(time_limit, 0.05), 2.0)
    safe_lines = min(max(lines, 1), 5)
    try:
        async with limited_operation(
            db,
            user=current.user,
            operation="stockfish_position",
            concurrency_group="engine",
            lock_ttl_seconds=30,
        ):
            return await analyze_position(
                current_fen, time_limit=safe_time_limit, multipv=safe_lines
            )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 - expose engine failure through the API
        raise HTTPException(status_code=500, detail=f"Wystąpił błąd silnika: {e!s}")


@app.post("/api/reset")
async def reset_game(
    game: ChessGame = Depends(get_game),
    current: CurrentAuth = Depends(require_csrf),
):
    """Wymusza reset gry do pozycji startowej."""
    game.reset()
    return {"fen": game.get_fen(), "history": game.get_history()}


@app.get("/api/chesscom/{username}/recent")
async def chesscom_recent_games(
    request: Request,
    username: str = Path(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$"),
    limit: int = 12,
    current: CurrentAuth = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db_session),
):
    await enforce_rate_limit(
        bucket="chesscom_ip",
        identity=request_ip(request),
        limit=60,
        window_seconds=300,
    )
    try:
        async with limited_operation(
            db,
            user=current.user,
            operation="chesscom_import",
            concurrency_group="external_api",
            lock_ttl_seconds=30,
        ):
            recent_games = await get_recent_games(username, min(max(limit, 1), 30))
            stored_by_external_id = await get_owned_games_by_external_ids(
                db,
                user=current.user,
                source=GameSource.CHESSCOM,
                external_ids=[
                    str(item["id"])
                    for item in recent_games
                    if item.get("id")
                ],
            )
            activity_game_ids = await games_with_analysis_activity(
                db,
                user=current.user,
                game_ids=[item.id for item in stored_by_external_id.values()],
            )
            for item in recent_games:
                stored = stored_by_external_id.get(str(item.get("id")))
                item["stored_game_id"] = str(stored.id) if stored else None
                item["has_analysis"] = bool(
                    stored and stored.id in activity_game_ids
                )
            return {"username": username, "games": recent_games}
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Nie udało się pobrać partii z Chess.com",
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Brak połączenia z Chess.com API")


@app.post("/api/import-game")
async def import_game(
    request: ImportGameRequest,
    game: ChessGame = Depends(get_game),
    current: CurrentAuth = Depends(require_csrf),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        metadata = {
            key: value
            for key, value in (request.metadata or {}).items()
            if key != "pgn"
        }
        response = game.load_pgn(request.pgn, metadata)
        if metadata.get("source") == GameSource.PGN.value:
            headers = response.get("headers", {})
            for key in ("white", "black", "result", "date", "site", "event"):
                header_value = headers.get(key.title())
                if header_value and key not in metadata:
                    metadata[key] = header_value
            game.imported_metadata = metadata
            response["metadata"] = metadata
        stored = await persist_imported_game(
            db,
            user=current.user,
            pgn=request.pgn,
            metadata=metadata,
        )
        await db.commit()
        metadata["source"] = stored.source.value
        game.imported_metadata = metadata
        game.imported_game_id = str(stored.id)
        response["metadata"] = metadata
        response["source"] = stored.source.value
        response["game_id"] = str(stored.id)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/import-position")
async def import_position(
    request: ImportPositionRequest,
    game: ChessGame = Depends(get_game),
    current: CurrentAuth = Depends(require_csrf),
):
    try:
        return game.load_fen(request.fen)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/imported-game/position")
async def imported_game_position(
    request: GamePositionRequest,
    game: ChessGame = Depends(get_game),
    current: CurrentAuth = Depends(require_csrf),
):
    try:
        return game.go_to_imported_ply(request.ply)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/analyze-game")
async def analyze_imported_game(
    request: ChatRequest,
    time_limit: float = 0.15,
    session_id: str = Depends(get_session_id),
    game: ChessGame = Depends(get_game),
    current: CurrentAuth = Depends(require_entitlement("ai_game_review", write=True)),
    db: AsyncSession = Depends(get_db_session),
):
    if not is_chess_request(request.message):
        raise HTTPException(status_code=400, detail=OUT_OF_SCOPE_MESSAGE)
    imported_game = game.get_imported_game()
    if not imported_game:
        raise HTTPException(
            status_code=400, detail="Najpierw zaimportuj zakończoną partię"
        )

    selected_model = get_default_model()

    current_task = asyncio.current_task()
    if current_task is None:
        raise HTTPException(
            status_code=500, detail="Nie udało się zarejestrować zadania analizy"
        )
    active_analysis_tasks[session_id] = current_task
    try:
        async with limited_operation(
            db,
            user=current.user,
            operation="ai_game_review",
            monthly_key="ai_game_review",
            concurrency_group="full_analysis",
            lock_ttl_seconds=600,
        ) as usage_details:
            engine_data = await analyze_game(
                imported_game["pgn"], time_limit=min(max(time_limit, 0.05), 1.0)
            )
            llm_result = await generate_game_analysis(
                pgn=imported_game["pgn"],
                engine_analysis=engine_data,
                metadata=imported_game["metadata"],
                user_prompt=request.message,
                model=selected_model,
            )
            usage_details.update(llm_result.usage)
            raw_game_id = imported_game.get("game_id")
            if not isinstance(raw_game_id, str):
                raise HTTPException(
                    status_code=409,
                    detail="Partia nie została trwale zapisana. Zaimportuj ją ponownie.",
                )
            analysis = await record_completed_analysis(
                db,
                user=current.user,
                game_id=uuid.UUID(raw_game_id),
                engine_result=engine_data,
                coach_response=llm_result.text,
            )
            await add_chat_messages(
                db,
                user=current.user,
                game_id=uuid.UUID(raw_game_id),
                messages=(
                    ("user", "game_review", request.message),
                    ("assistant", "game_review", llm_result.text),
                ),
                fen=game.get_fen(),
            )
        last_ai_analyses[session_id] = llm_result.text
        return {
            "response": llm_result.text,
            "engine_analysis": engine_data,
            "analysis_id": str(analysis.id),
        }
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Analiza została przerwana")
    except HTTPException:
        raise
    except LLMServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as e:  # noqa: BLE001 - normalize analysis pipeline failures
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if active_analysis_tasks.get(session_id) is current_task:
            active_analysis_tasks.pop(session_id, None)


@app.post("/api/chat")
async def chat_with_agent(
    request: ChatRequest,
    session_id: str = Depends(get_session_id),
    game: ChessGame = Depends(get_game),
    current: CurrentAuth = Depends(require_entitlement("ai_game_review", write=True)),
    db: AsyncSession = Depends(get_db_session),
    time_limit: float = 2.0,  # Domyślnie dajemy Krakenowi 2 sekundy, jeśli frontend nic nie prześle
    lines: int = 3,  # Domyślnie 3 linie MultiPV
):
    """
    Endpoint analizy LLM. Zbiera dane z gry i zewnętrznych źródeł,
    przyjmując parametry czasu i głębokości silnika prosto z URL.
    """
    if is_full_game_analysis_request(request.message):
        detail = FULL_GAME_ANALYSIS_MESSAGE
        if not game.get_imported_game():
            detail = "Najpierw wybierz partię, a następnie użyj przycisku „Analizuj całą partię”."
        return {"response": detail, "action": "use_game_review"}

    if not is_chess_request(request.message):
        raise HTTPException(status_code=400, detail=OUT_OF_SCOPE_MESSAGE)

    current_fen = game.get_fen()
    selected_model = get_default_model()

    current_task = asyncio.current_task()
    if current_task is None:
        raise HTTPException(
            status_code=500, detail="Nie udało się zarejestrować zadania analizy"
        )
    active_analysis_tasks[session_id] = current_task
    try:
        async with limited_operation(
            db,
            user=current.user,
            operation="ai_chat",
            monthly_key="ai_chat",
            concurrency_group="full_analysis",
            lock_ttl_seconds=300,
        ) as usage_details:
            stockfish_data = await analyze_position(
                current_fen,
                time_limit=min(max(time_limit, 0.05), 2.0),
                multipv=min(max(lines, 1), 5),
            )
            fallback_opening = identify_opening(game.get_history())
            try:
                lichess_data = await get_opening_explorer_data(
                    current_fen,
                    fallback_opening=fallback_opening,
                )
            except (httpx.HTTPStatusError, httpx.RequestError):
                lichess_data = {
                    "fen": current_fen,
                    "opening_name": fallback_opening.get("name")
                    if fallback_opening
                    else None,
                    "opening_eco": fallback_opening.get("eco")
                    if fallback_opening
                    else None,
                    "opening_is_fallback": bool(fallback_opening),
                    "total_games_analyzed": 0,
                    "top_moves": [],
                }
            llm_result = await generate_chess_analysis(
                fen=current_fen,
                lichess_data=lichess_data,
                stockfish_data=stockfish_data,
                user_prompt=request.message,
                model=selected_model,
            )
            usage_details.update(llm_result.usage)

            chat_game_id = await current_owned_game_id(
                db, game=game, current=current
            )
            if chat_game_id is not None:
                await add_chat_messages(
                    db,
                    user=current.user,
                    game_id=chat_game_id,
                    messages=(
                        ("user", "position", request.message),
                        ("assistant", "position", llm_result.text),
                    ),
                    fen=current_fen,
                )

        last_ai_analyses[session_id] = llm_result.text
        return {"response": llm_result.text}

    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Analiza została przerwana")
    except HTTPException:
        raise
    except LLMServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as e:  # noqa: BLE001 - normalize chat pipeline failures
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if active_analysis_tasks.get(session_id) is current_task:
            active_analysis_tasks.pop(session_id, None)


@app.post("/api/chat/translate")
async def translate_chat_analysis(
    session_id: str = Depends(get_session_id),
    game: ChessGame = Depends(get_game),
    current: CurrentAuth = Depends(require_entitlement("ai_game_review", write=True)),
    db: AsyncSession = Depends(get_db_session),
):
    chat_game_id = await current_owned_game_id(db, game=game, current=current)
    stored_analysis = (
        await latest_translatable_analysis(
            db, user=current.user, game_id=chat_game_id
        )
        if chat_game_id is not None
        else None
    )
    source_analysis = (
        stored_analysis.content if stored_analysis else last_ai_analyses.get(session_id)
    )
    if not source_analysis:
        raise HTTPException(
            status_code=409,
            detail="Najpierw poproś RajkoAI o analizę szachową.",
        )
    try:
        async with limited_operation(
            db,
            user=current.user,
            operation="ai_chat",
            monthly_key="ai_chat",
            concurrency_group="full_analysis",
            lock_ttl_seconds=180,
        ) as usage_details:
            llm_result = await translate_analysis_to_english(source_analysis[:10_000])
            usage_details.update(llm_result.usage)
            usage_details["operation"] = "translation_en"
            if chat_game_id is not None:
                await add_chat_messages(
                    db,
                    user=current.user,
                    game_id=chat_game_id,
                    messages=(("assistant", "translation", llm_result.text),),
                    fen=game.get_fen(),
                )
        return {"response": llm_result.text}
    except LLMServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/cancel-analysis")
async def cancel_analysis(
    session_id: str = Depends(get_session_id),
    current: CurrentAuth = Depends(require_csrf),
):
    task = active_analysis_tasks.get(session_id)
    if task is None or task.done():
        return {"cancelled": False}

    task.cancel()
    return {"cancelled": True}


@app.get("/api/games")
async def game_history(
    limit: int = 30,
    offset: int = 0,
    source: GameSource | None = None,
    current: CurrentAuth = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db_session),
):
    models = await list_owned_games(
        db,
        user=current.user,
        limit=min(max(limit, 1), 100),
        offset=max(offset, 0),
        source=source,
    )
    activity_game_ids = await games_with_analysis_activity(
        db, user=current.user, game_ids=[model.id for model in models]
    )
    return {
        "games": [
            game_response(model, has_analysis=model.id in activity_game_ids)
            for model in models
        ]
    }


@app.get("/api/games/{game_id}")
async def game_history_detail(
    game_id: uuid.UUID,
    current: CurrentAuth = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db_session),
):
    model = await get_owned_game(
        db, user=current.user, game_id=game_id, with_analyses=True
    )
    if model is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono partii")
    analyses = sorted(model.analyses, key=lambda item: item.created_at, reverse=True)
    return {
        "game": game_response(
            model,
            include_pgn=True,
            has_analysis=bool(model.analyses or model.chat_messages),
        ),
        "analyses": [analysis_response(item) for item in analyses],
    }


@app.get("/api/games/{game_id}/chat")
async def game_chat_history(
    game_id: uuid.UUID,
    current: CurrentAuth = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db_session),
):
    model = await get_owned_game(
        db, user=current.user, game_id=game_id, with_analyses=True
    )
    if model is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono partii")
    messages = await list_chat_messages(
        db, user=current.user, game_id=game_id, limit=200
    )
    return {"messages": [chat_message_response(item) for item in messages]}


@app.delete("/api/games/{game_id}/chat")
async def delete_game_chat_history(
    game_id: uuid.UUID,
    current: CurrentAuth = Depends(require_csrf),
    db: AsyncSession = Depends(get_db_session),
):
    model = await get_owned_game(
        db, user=current.user, game_id=game_id, with_analyses=True
    )
    if model is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono partii")
    await clear_chat_messages(db, user=current.user, game_id=game_id)
    await db.commit()
    return {"cleared": True, "has_analysis": bool(model.analyses)}


@app.post("/api/games/{game_id}/open")
async def open_historical_game(
    game_id: uuid.UUID,
    game: ChessGame = Depends(get_game),
    current: CurrentAuth = Depends(require_csrf),
    db: AsyncSession = Depends(get_db_session),
):
    model = await get_owned_game(db, user=current.user, game_id=game_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono partii")
    metadata = {**model.metadata_json, "source": model.source.value}
    response = game.load_pgn(
        model.pgn,
        metadata,
        game_id=str(model.id),
    )
    response["pgn"] = model.pgn
    response["source"] = model.source.value
    return response
