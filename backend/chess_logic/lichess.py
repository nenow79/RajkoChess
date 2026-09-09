import os
import re
from datetime import datetime, timezone
from io import StringIO
from typing import Any

import chess.pgn
import httpx

LICHESS_EXPLORER_URL = "https://explorer.lichess.ovh/lichess"
LICHESS_GAMES_URL = "https://lichess.org/api/games/user"
LICHESS_HEADERS = {
    "Accept": "application/x-chess-pgn",
    "User-Agent": "RajkoChess/1.0 (https://rajko.pl/chess/)",
}
LICHESS_GAME_ID_PATTERN = re.compile(r"lichess\.org/([A-Za-z0-9]{8})")


async def get_recent_games(username: str, limit: int = 12) -> list[dict[str, Any]]:
    """Return the user's latest completed games played with standard rules."""
    timeout = httpx.Timeout(10.0, connect=5.0)
    params = {
        "max": min(max(limit, 1), 30),
        "moves": "true",
        "clocks": "false",
        "evals": "false",
        "opening": "false",
        "finished": "true",
        "perfType": "ultraBullet,bullet,blitz,rapid,classical,correspondence",
    }
    async with httpx.AsyncClient(headers=LICHESS_HEADERS, timeout=timeout) as client:
        response = await client.get(f"{LICHESS_GAMES_URL}/{username}", params=params)
        response.raise_for_status()
    return _parse_games(response.text, username, limit)


def _parse_games(pgn_export: str, username: str, limit: int) -> list[dict[str, Any]]:
    stream = StringIO(pgn_export)
    games: list[dict[str, Any]] = []
    while len(games) < limit:
        parsed = chess.pgn.read_game(stream)
        if parsed is None:
            break
        variant = parsed.headers.get("Variant", "Standard").casefold()
        if variant not in {"standard", "chess"}:
            continue
        exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
        games.append(_summarize_game(parsed, parsed.accept(exporter), username))
    return games


def _summarize_game(
    game: chess.pgn.Game, pgn: str, username: str
) -> dict[str, Any]:
    headers = game.headers
    white = headers.get("White", "")
    black = headers.get("Black", "")
    player_is_white = white.casefold() == username.casefold()
    player = white if player_is_white else black
    opponent = black if player_is_white else white
    result = headers.get("Result", "*")
    player_result = (
        "draw"
        if result == "1/2-1/2"
        else "win"
        if (result == "1-0") == player_is_white
        else "loss"
    )
    site = headers.get("Site", "")
    id_match = LICHESS_GAME_ID_PATTERN.search(site)
    external_id = headers.get("GameId") or (
        id_match.group(1) if id_match else site.rstrip("/").split("/")[-1][:8]
    )
    played_at = _played_at(
        headers.get("UTCDate") or headers.get("Date"), headers.get("UTCTime")
    )
    total_plies = len(list(game.mainline_moves()))

    return {
        "id": external_id,
        "url": site or None,
        "pgn": pgn,
        "played_at": played_at,
        "time_class": headers.get("Speed", "").casefold()
        or _speed_from_time_control(
            headers.get("TimeControl"), headers.get("Event", "")
        ),
        "time_control": headers.get("TimeControl"),
        "rated": headers.get("Event", "").casefold().startswith("rated"),
        "color": "white" if player_is_white else "black",
        "result": player_result,
        "rating": _integer(
            headers.get("WhiteElo" if player_is_white else "BlackElo")
        ),
        "opponent": opponent,
        "opponent_rating": _integer(
            headers.get("BlackElo" if player_is_white else "WhiteElo")
        ),
        "move_count": (total_plies + 1) // 2,
        "total_plies": total_plies,
        "source": "lichess",
        "player": player,
    }


def _integer(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _speed_from_time_control(time_control: str | None, event: str) -> str:
    if "correspondence" in event.casefold():
        return "correspondence"
    if not time_control:
        return "unknown"
    try:
        base, increment = (int(part) for part in time_control.split("+", 1))
    except (TypeError, ValueError):
        return "unknown"
    estimated_seconds = base + 40 * increment
    if estimated_seconds < 30:
        return "ultrabullet"
    if estimated_seconds < 180:
        return "bullet"
    if estimated_seconds < 480:
        return "blitz"
    if estimated_seconds < 1500:
        return "rapid"
    return "classical"


def _played_at(date: str | None, time: str | None) -> str | None:
    if not date or date == "????.??.??":
        return None
    try:
        parsed = datetime.strptime(
            f"{date} {time or '00:00:00'}", "%Y.%m.%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return parsed.isoformat()


async def get_opening_explorer_data(
    fen: str,
    max_moves: int = 5,
    ratings: str | None = None,
    fallback_opening: dict[str, Any] | None = None,
) -> dict:
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
        "speeds": "blitz,rapid,classical",
    }

    # Jeśli podano filtry rankingowe, dołączamy je do zapytania
    if ratings:
        params["ratings"] = ratings

    async with httpx.AsyncClient() as client:
        response = await client.get(
            LICHESS_EXPLORER_URL, headers=headers, params=params, timeout=5.0
        )

        response.raise_for_status()
        data = response.json()

        # Zabezpieczenie przed wartością null z Lichessa
        opening_data = data.get("opening") or {}
        opening_name = opening_data.get("name")
        opening_eco = opening_data.get("eco")
        opening_is_fallback = False

        if not opening_name and fallback_opening:
            opening_name = fallback_opening.get("name")
            opening_eco = fallback_opening.get("eco")
            opening_is_fallback = bool(opening_name)

        total_games = data.get("white", 0) + data.get("draws", 0) + data.get("black", 0)
        processed_moves = []

        for move in data.get("moves", []):
            move_total = move["white"] + move["draws"] + move["black"]
            if move_total == 0:
                continue

            processed_moves.append(
                {
                    "uci": move["uci"],
                    "san": move["san"],
                    "games_count": move_total,
                    "play_rate_pct": round((move_total / total_games) * 100, 1)
                    if total_games > 0
                    else 0,
                    "white_win_pct": round((move["white"] / move_total) * 100, 1),
                    "draw_pct": round((move["draws"] / move_total) * 100, 1),
                    "black_win_pct": round((move["black"] / move_total) * 100, 1),
                }
            )

        return {
            "fen": fen,
            "opening_name": opening_name,  # Dodane: nazwa otwarcia
            "opening_eco": opening_eco,  # Dodane: kod ECO, np. "C31"
            "opening_is_fallback": opening_is_fallback,
            "total_games_analyzed": total_games,
            "top_moves": processed_moves,
        }
