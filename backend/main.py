# main.py
import asyncio
import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware # Dodany import
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional

from chess_logic.game import ChessGame
from chess_logic.lichess import get_opening_explorer_data
from chess_logic.engine import analyze_position
from chess_logic.engine import analyze_game
from chess_logic.chesscom import get_recent_games
from chess_logic.llm_agent import (
    AVAILABLE_MODELS,
    AVAILABLE_MODEL_IDS,
    generate_chess_analysis,
    generate_game_analysis,
    get_default_model,
)

# Ładowanie zmiennych środowiskowych z .env
load_dotenv()

app = FastAPI(title="Chess API")

class ChatRequest(BaseModel):
    message: str = ""
    model: Optional[str] = None

class ImportGameRequest(BaseModel):
    pgn: str
    metadata: Optional[dict] = None

class GamePositionRequest(BaseModel):
    ply: int

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], # Porty Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_SESSION_ID = "default"

# Stan gry trzymamy osobno dla każdej przeglądarki/użytkownika.
games: dict[str, ChessGame] = {}
active_analysis_tasks: dict[str, asyncio.Task] = {}


def get_session_id(x_session_id: str | None = Header(default=None, alias="X-Session-Id")) -> str:
    session_id = (x_session_id or DEFAULT_SESSION_ID).strip()
    return session_id[:128] or DEFAULT_SESSION_ID


def get_game(session_id: str = Depends(get_session_id)) -> ChessGame:
    if session_id not in games:
        games[session_id] = ChessGame()
    return games[session_id]

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
    success = game.make_move(request.uci, preserve_imported_context=request.preserve_imported_context)
    if not success:
        raise HTTPException(status_code=400, detail="Nieprawidłowy lub nielegalny ruch")
    
    return {
        "fen": game.get_fen(),
        "history": game.get_history()
    }

@app.post("/api/undo")
async def undo_move(request: UndoRequest | None = None, game: ChessGame = Depends(get_game)):
    """Cofa ostatni ruch na szachownicy."""
    preserve_imported_context = request.preserve_imported_context if request else False
    success = game.undo_move(preserve_imported_context=preserve_imported_context)
    if not success:
        raise HTTPException(status_code=400, detail="Brak ruchów do cofnięcia")
    
    return {
        "fen": game.get_fen(),
        "history": game.get_history()
    }

@app.get("/api/history")
async def get_history(game: ChessGame = Depends(get_game)):
    """Zwraca historię ruchów w obecnej partii."""
    return {"history": game.get_history()}


@app.get("/api/explorer")
async def get_explorer_stats(
    ratings: Optional[str] = None,
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
            detail=f"Błąd zewnętrznego API Lichess: {e.response.text}"
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Brak połączenia z Lichess API")


@app.get("/api/analyze")
async def analyze_current_position(
    time_limit: float = 0.5,
    lines: int = 3,
    game: ChessGame = Depends(get_game),
):
    """
    Zwraca ocenę bieżącej pozycji ze Stockfisha.
    - **time_limit**: czas (w sekundach), jaki silnik ma na przemyślenie ruchu.
    - **lines**: ilość rozważanych najlepszych ruchów (MultiPV).
    """
    current_fen = game.get_fen()

    try:
        # Przekazujemy argument lines jako multipv
        analysis = await analyze_position(current_fen, time_limit=time_limit, multipv=lines)
        return analysis
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Wystąpił błąd silnika: {str(e)}")

@app.post("/api/reset")
async def reset_game(game: ChessGame = Depends(get_game)):
    """Wymusza reset gry do pozycji startowej."""
    game.reset()
    return {
        "fen": game.get_fen(),
        "history": game.get_history()
    }


@app.get("/api/chesscom/{username}/recent")
async def chesscom_recent_games(username: str, limit: int = 12):
    try:
        return {"username": username, "games": await get_recent_games(username, min(max(limit, 1), 30))}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Nie udało się pobrać partii z Chess.com")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Brak połączenia z Chess.com API")


@app.post("/api/import-game")
async def import_game(request: ImportGameRequest, game: ChessGame = Depends(get_game)):
    try:
        metadata = {
            key: value for key, value in (request.metadata or {}).items()
            if key != "pgn"
        }
        return game.load_pgn(request.pgn, metadata)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/imported-game/position")
async def imported_game_position(request: GamePositionRequest, game: ChessGame = Depends(get_game)):
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
):
    imported_game = game.get_imported_game()
    if not imported_game:
        raise HTTPException(status_code=400, detail="Najpierw zaimportuj zakończoną partię")

    selected_model = request.model or get_default_model()
    if selected_model not in AVAILABLE_MODEL_IDS:
        raise HTTPException(status_code=400, detail="Nieobsługiwany model LLM")

    current_task = asyncio.current_task()
    active_analysis_tasks[session_id] = current_task
    try:
        engine_data = await analyze_game(imported_game["pgn"], time_limit=min(max(time_limit, 0.05), 1.0))
        response = await generate_game_analysis(
            pgn=imported_game["pgn"],
            engine_analysis=engine_data,
            metadata=imported_game["metadata"],
            user_prompt=request.message,
            model=selected_model,
        )
        return {"response": response, "model": selected_model, "engine_analysis": engine_data}
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Analiza została przerwana")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if active_analysis_tasks.get(session_id) is current_task:
            active_analysis_tasks.pop(session_id, None)


@app.post("/api/chat")
async def chat_with_agent(
        request: ChatRequest,
        session_id: str = Depends(get_session_id),
        game: ChessGame = Depends(get_game),
        time_limit: float = 2.0,  # Domyślnie dajemy Krakenowi 2 sekundy, jeśli frontend nic nie prześle
        lines: int = 3  # Domyślnie 3 linie MultiPV
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
    active_analysis_tasks[session_id] = current_task
    try:
        # Przekazujemy parametry pobrane dynamicznie z adresu URL
        stockfish_data = await analyze_position(current_fen, time_limit=time_limit, multipv=lines)
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
            model=selected_model
        )

        return {"response": analysis_text, "model": selected_model}

    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Analiza została przerwana")
    except Exception as e:
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
