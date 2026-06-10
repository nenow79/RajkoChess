from datetime import datetime, timezone

import httpx


BASE_URL = "https://api.chess.com/pub/player"
HEADERS = {
    "User-Agent": "RajkoChessAnalyser/1.0 (local personal chess analysis app)",
}


async def get_recent_games(username: str, limit: int = 12) -> list[dict]:
    """Returns the player's most recent completed standard chess games."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=20.0) as client:
        archives_response = await client.get(f"{BASE_URL}/{username}/games/archives")
        archives_response.raise_for_status()
        archives = archives_response.json().get("archives", [])

        recent_games = []
        for archive_url in reversed(archives):
            response = await client.get(archive_url)
            response.raise_for_status()

            standard_games = [
                game for game in response.json().get("games", [])
                if game.get("rules") == "chess"
            ]
            recent_games.extend(reversed(standard_games))

            if len(recent_games) >= limit:
                break

    return [_summarize_game(game, username) for game in recent_games[:limit]]


def _summarize_game(game: dict, username: str) -> dict:
    white = game.get("white", {})
    black = game.get("black", {})
    username_lower = username.lower()
    player_is_white = white.get("username", "").lower() == username_lower
    player = white if player_is_white else black
    opponent = black if player_is_white else white
    end_time = game.get("end_time")

    return {
        "id": game.get("url", "").rstrip("/").split("/")[-1],
        "url": game.get("url"),
        "pgn": game.get("pgn"),
        "fen": game.get("fen"),
        "played_at": (
            datetime.fromtimestamp(end_time, tz=timezone.utc).isoformat()
            if end_time else None
        ),
        "time_class": game.get("time_class"),
        "time_control": game.get("time_control"),
        "rated": game.get("rated", False),
        "color": "white" if player_is_white else "black",
        "result": player.get("result"),
        "rating": player.get("rating"),
        "opponent": opponent.get("username"),
        "opponent_rating": opponent.get("rating"),
        "accuracies": game.get("accuracies"),
    }
