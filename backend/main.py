# main.py
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # Dodany import
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional

from chess_logic.game import ChessGame
from chess_logic.lichess import get_opening_explorer_data
from chess_logic.engine import analyze_position
from chess_logic.llm_agent import generate_chess_analysis

# Ładowanie zmiennych środowiskowych z .env
load_dotenv()

app = FastAPI(title="Chess API")

class ChatRequest(BaseModel):
    message: str = ""

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], # Porty Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Na ten moment trzymamy stan jednej gry w pamięci
game = ChessGame()

class MoveRequest(BaseModel):
    uci: str  # np. "e2e4", "g1f3"

@app.get("/api/position")
async def get_position():
    """Zwraca bieżącą pozycję na szachownicy."""
    return {"fen": game.get_fen()}

@app.post("/api/move")
async def make_move(request: MoveRequest):
    """Wykonuje ruch na szachownicy."""
    success = game.make_move(request.uci)
    if not success:
        raise HTTPException(status_code=400, detail="Nieprawidłowy lub nielegalny ruch")
    
    return {
        "fen": game.get_fen(),
        "history": game.get_history()
    }

@app.post("/api/undo")
async def undo_move():
    """Cofa ostatni ruch na szachownicy."""
    success = game.undo_move()
    if not success:
        raise HTTPException(status_code=400, detail="Brak ruchów do cofnięcia")
    
    return {
        "fen": game.get_fen(),
        "history": game.get_history()
    }

@app.get("/api/history")
async def get_history():
    """Zwraca historię ruchów w obecnej partii."""
    return {"history": game.get_history()}


@app.get("/api/explorer")
async def get_explorer_stats(ratings: Optional[str] = None, moves: int = 5):
    """
    Zwraca statystyki z bazy Lichess dla bieżącej pozycji na szachownicy.

    Opcjonalne filtry:
    - **ratings**: np. "1600,1800" (dostępne kubełki: 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2500)
    - **moves**: ilość zwracanych najpopularniejszych ruchów (domyślnie 5)
    """
    current_fen = game.get_fen()

    try:
        data = await get_opening_explorer_data(current_fen, max_moves=moves, ratings=ratings)
        return data
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Błąd zewnętrznego API Lichess: {e.response.text}"
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Brak połączenia z Lichess API")


@app.get("/api/analyze")
async def analyze_current_position(time_limit: float = 0.5, lines: int = 3):
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
async def reset_game():
    """Wymusza reset gry do pozycji startowej."""
    game.reset()
    return {
        "fen": game.get_fen(),
        "history": game.get_history()
    }


@app.post("/api/chat")
async def chat_with_agent(
        request: ChatRequest,
        time_limit: float = 2.0,  # Domyślnie dajemy Krakenowi 2 sekundy, jeśli frontend nic nie prześle
        lines: int = 3  # Domyślnie 3 linie MultiPV
):
    """
    Endpoint analizy LLM. Zbiera dane z gry i zewnętrznych źródeł,
    przyjmując parametry czasu i głębokości silnika prosto z URL.
    """
    current_fen = game.get_fen()

    try:
        # Przekazujemy parametry pobrane dynamicznie z adresu URL
        stockfish_data = await analyze_position(current_fen, time_limit=time_limit, multipv=lines)
        lichess_data = await get_opening_explorer_data(current_fen)

        # Wysyłamy bogaty kontekst do Agenta LLM
        analysis_text = await generate_chess_analysis(
            fen=current_fen,
            lichess_data=lichess_data,
            stockfish_data=stockfish_data,
            user_prompt=request.message
        )

        return {"response": analysis_text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))