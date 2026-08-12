# main.py
import asyncio

import httpx
from admin.router import router as admin_router
from auth.audit import write_audit
from auth.dependencies import CurrentAuth, get_current_auth, require_csrf
from auth.policies import require_entitlement
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
from chess_logic.lichess import get_opening_explorer_data
from chess_logic.llm_agent import (
    AVAILABLE_MODEL_IDS,
    AVAILABLE_MODELS,
    generate_bot_profile,
    generate_chess_analysis,
    generate_game_analysis,
    get_default_model,
)
from chess_logic.openings import find_opening, resolve_opening, search_openings
from db.models import BotVisibility
from db.session import get_db_session
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # Dodany import
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

# Ładowanie zmiennych środowiskowych z .env
load_dotenv()

app = FastAPI(title="Chess API")
app.include_router(auth_router)
app.include_router(admin_router)


class ChatRequest(BaseModel):
    message: str = ""
    model: str | None = None


class ImportGameRequest(BaseModel):
    pgn: str
    metadata: dict | None = None


class GamePositionRequest(BaseModel):
    ply: int


class BotStartRequest(BaseModel):
    bot_id: str
    player_color: str = "random"
    llm_commentary: bool = False


class BotMoveRequest(BaseModel):
    uci: str


class BotDraftRequest(BaseModel):
    description: str
    model: str | None = None


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
bot_games = BotGameManager()


def get_session_id(current: CurrentAuth = Depends(get_current_auth)) -> str:
    """Zwraca niepodrabialny klucz stanu z sesji zweryfikowanej w PostgreSQL."""
    return str(current.session.id)


def get_game(session_id: str = Depends(get_session_id)) -> ChessGame:
    if session_id not in games:
        games[session_id] = ChessGame()
    return games[session_id]


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
    current: CurrentAuth = Depends(get_current_auth),
):
    if not request.description.strip():
        raise HTTPException(status_code=400, detail="Opisz charakter bota")
    if request.model and request.model not in AVAILABLE_MODEL_IDS:
        raise HTTPException(status_code=400, detail="Nieobsługiwany model LLM")
    try:
        draft = await generate_bot_profile(request.description, request.model)
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
    except Exception as exc:  # noqa: BLE001 - normalize external provider failures
        raise HTTPException(
            status_code=502, detail=f"Nie udało się utworzyć profilu: {exc}"
        )


@app.post("/api/bot-games/start")
async def start_bot_game(
    request: BotStartRequest,
    session_id: str = Depends(get_session_id),
    current: CurrentAuth = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db_session),
):
    if request.player_color not in ("white", "black", "random"):
        raise HTTPException(status_code=400, detail="Nieprawidłowy kolor")
    try:
        model = await get_visible_bot(db, bot_id=request.bot_id, user=current.user)
        bot = bot_response(model, current.user)
    except BotNotFoundError:
        raise HTTPException(status_code=404, detail="Nie znaleziono bota")
    try:
        async with bot_games.lock(session_id):
            return await bot_games.start(
                session_id,
                bot,
                request.player_color,
                llm_commentary=request.llm_commentary,
            )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/bot-games/current")
async def current_bot_game(session_id: str = Depends(get_session_id)):
    game = bot_games.games.get(session_id)
    return game.response() if game else {"status": "none"}


@app.post("/api/bot-games/move")
async def bot_game_move(
    request: BotMoveRequest, session_id: str = Depends(get_session_id)
):
    try:
        async with bot_games.lock(session_id):
            return await bot_games.move(session_id, request.uci)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/bot-games/resign")
async def resign_bot_game(session_id: str = Depends(get_session_id)):
    try:
        return bot_games.resign(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/bot-games/draw-offer")
async def bot_game_draw(session_id: str = Depends(get_session_id)):
    try:
        return bot_games.draw_offer(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/bot-games/to-analysis")
async def bot_game_to_analysis(
    session_id: str = Depends(get_session_id), game: ChessGame = Depends(get_game)
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
    """Zwraca bieżącą pozycję na szachownicy."""
    return {"fen": game.get_fen()}


@app.post("/api/move")
async def make_move(request: MoveRequest, game: ChessGame = Depends(get_game)):
    """Wykonuje ruch na szachownicy."""
    success = game.make_move(
        request.uci, preserve_imported_context=request.preserve_imported_context
    )
    if not success:
        raise HTTPException(status_code=400, detail="Nieprawidłowy lub nielegalny ruch")

    return {"fen": game.get_fen(), "history": game.get_history()}


@app.post("/api/undo")
async def undo_move(
    request: UndoRequest | None = None, game: ChessGame = Depends(get_game)
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
            fallback_fens=game.get_ancestor_fens(),
        )
        return data
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Błąd zewnętrznego API Lichess: {e.response.text}",
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Brak połączenia z Lichess API")


@app.get("/api/analyze")
async def analyze_current_position(
    time_limit: float = 0.5,
    lines: int = 3,
    game: ChessGame = Depends(get_game),
    current: CurrentAuth = Depends(require_entitlement("basic_analysis")),
):
    """
    Zwraca ocenę bieżącej pozycji ze Stockfisha.
    - **time_limit**: czas (w sekundach), jaki silnik ma na przemyślenie ruchu.
    - **lines**: ilość rozważanych najlepszych ruchów (MultiPV).
    """
    current_fen = game.get_fen()

    try:
        # Przekazujemy argument lines jako multipv
        analysis = await analyze_position(
            current_fen, time_limit=time_limit, multipv=lines
        )
        return analysis
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:  # noqa: BLE001 - expose engine failure through the API
        raise HTTPException(status_code=500, detail=f"Wystąpił błąd silnika: {e!s}")


@app.post("/api/reset")
async def reset_game(game: ChessGame = Depends(get_game)):
    """Wymusza reset gry do pozycji startowej."""
    game.reset()
    return {"fen": game.get_fen(), "history": game.get_history()}


@app.get("/api/chesscom/{username}/recent")
async def chesscom_recent_games(username: str, limit: int = 12):
    try:
        return {
            "username": username,
            "games": await get_recent_games(username, min(max(limit, 1), 30)),
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Nie udało się pobrać partii z Chess.com",
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Brak połączenia z Chess.com API")


@app.post("/api/import-game")
async def import_game(request: ImportGameRequest, game: ChessGame = Depends(get_game)):
    try:
        metadata = {
            key: value
            for key, value in (request.metadata or {}).items()
            if key != "pgn"
        }
        return game.load_pgn(request.pgn, metadata)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/imported-game/position")
async def imported_game_position(
    request: GamePositionRequest, game: ChessGame = Depends(get_game)
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
    current: CurrentAuth = Depends(require_entitlement("ai_game_review")),
):
    imported_game = game.get_imported_game()
    if not imported_game:
        raise HTTPException(
            status_code=400, detail="Najpierw zaimportuj zakończoną partię"
        )

    selected_model = request.model or get_default_model()
    if selected_model not in AVAILABLE_MODEL_IDS:
        raise HTTPException(status_code=400, detail="Nieobsługiwany model LLM")

    current_task = asyncio.current_task()
    if current_task is None:
        raise HTTPException(
            status_code=500, detail="Nie udało się zarejestrować zadania analizy"
        )
    active_analysis_tasks[session_id] = current_task
    try:
        engine_data = await analyze_game(
            imported_game["pgn"], time_limit=min(max(time_limit, 0.05), 1.0)
        )
        response = await generate_game_analysis(
            pgn=imported_game["pgn"],
            engine_analysis=engine_data,
            metadata=imported_game["metadata"],
            user_prompt=request.message,
            model=selected_model,
        )
        return {
            "response": response,
            "model": selected_model,
            "engine_analysis": engine_data,
        }
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Analiza została przerwana")
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
    current: CurrentAuth = Depends(require_entitlement("ai_game_review")),
    time_limit: float = 2.0,  # Domyślnie dajemy Krakenowi 2 sekundy, jeśli frontend nic nie prześle
    lines: int = 3,  # Domyślnie 3 linie MultiPV
):
    """
    Endpoint analizy LLM. Zbiera dane z gry i zewnętrznych źródeł,
    przyjmując parametry czasu i głębokości silnika prosto z URL.
    """
    current_fen = game.get_fen()
    selected_model = request.model or get_default_model()

    if selected_model not in AVAILABLE_MODEL_IDS:
        raise HTTPException(status_code=400, detail="Nieobsługiwany model LLM")

    current_task = asyncio.current_task()
    if current_task is None:
        raise HTTPException(
            status_code=500, detail="Nie udało się zarejestrować zadania analizy"
        )
    active_analysis_tasks[session_id] = current_task
    try:
        # Przekazujemy parametry pobrane dynamicznie z adresu URL
        stockfish_data = await analyze_position(
            current_fen, time_limit=time_limit, multipv=lines
        )
        lichess_data = await get_opening_explorer_data(
            current_fen,
            fallback_fens=game.get_ancestor_fens(),
        )

        # Wysyłamy bogaty kontekst do Agenta LLM
        analysis_text = await generate_chess_analysis(
            fen=current_fen,
            lichess_data=lichess_data,
            stockfish_data=stockfish_data,
            user_prompt=request.message,
            model=selected_model,
        )

        return {"response": analysis_text, "model": selected_model}

    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Analiza została przerwana")
    except Exception as e:  # noqa: BLE001 - normalize chat pipeline failures
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if active_analysis_tasks.get(session_id) is current_task:
            active_analysis_tasks.pop(session_id, None)


@app.post("/api/cancel-analysis")
async def cancel_analysis(session_id: str = Depends(get_session_id)):
    task = active_analysis_tasks.get(session_id)
    if task is None or task.done():
        return {"cancelled": False}

    task.cancel()
    return {"cancelled": True}


@app.get("/api/models")
async def get_models():
    """Zwraca modele LLM dostępne w interfejsie."""
    return {
        "default_model": get_default_model(),
        "models": AVAILABLE_MODELS,
    }
