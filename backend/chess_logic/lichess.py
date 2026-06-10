import os
import httpx
from typing import Optional

LICHESS_EXPLORER_URL = "https://explorer.lichess.ovh/lichess"


async def get_opening_explorer_data(fen: str, max_moves: int = 5, ratings: Optional[str] = None) -> dict:
    """
    Pobiera statystyki z Lichess Explorer API.
    """
    token = os.getenv("LICHESS_API_TOKEN")

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        print("Ostrzeżenie: Brak LICHESS_API_TOKEN w pliku .env")

    # Podstawowe parametry
    params = {
        "fen": fen,
        "moves": max_moves,
        "variant": "standard",
        "speeds": "blitz,rapid,classical"
    }

    # Jeśli podano filtry rankingowe, dołączamy je do zapytania
    if ratings:
        params["ratings"] = ratings

    async with httpx.AsyncClient() as client:
        response = await client.get(
            LICHESS_EXPLORER_URL,
            headers=headers,
            params=params,
            timeout=5.0
        )

        response.raise_for_status()
        data = response.json()

        # Zabezpieczenie przed wartością null z Lichessa
        opening_data = data.get("opening") or {}
        opening_name = opening_data.get("name")
        opening_eco = opening_data.get("eco")

        total_games = data.get("white", 0) + data.get("draws", 0) + data.get("black", 0)
        processed_moves = []

        for move in data.get("moves", []):
            move_total = move["white"] + move["draws"] + move["black"]
            if move_total == 0:
                continue

            processed_moves.append({
                "uci": move["uci"],
                "san": move["san"],
                "games_count": move_total,
                "play_rate_pct": round((move_total / total_games) * 100, 1) if total_games > 0 else 0,
                "white_win_pct": round((move["white"] / move_total) * 100, 1),
                "draw_pct": round((move["draws"] / move_total) * 100, 1),
                "black_win_pct": round((move["black"] / move_total) * 100, 1),
            })

        return {
            "fen": fen,
            "opening_name": opening_name,  # Dodane: nazwa otwarcia
            "opening_eco": opening_eco,  # Dodane: kod ECO, np. "C31"
            "total_games_analyzed": total_games,
            "top_moves": processed_moves
        }