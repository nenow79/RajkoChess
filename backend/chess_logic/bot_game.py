import asyncio
import math
import os
import random
import time
from dataclasses import dataclass, field

import chess
import chess.engine
import chess.pgn
from chess_logic.llm_agent import (
    generate_bot_game_greeting,
    generate_bot_move_commentary,
)
from chess_logic.openings import find_opening

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}
DEFAULT_BOT_ELO_OFFSET = -100
STOCKFISH_MIN_UCI_ELO = 1320


def configured_bot_elo_offset() -> int:
    try:
        offset = int(os.getenv("BOT_GLOBAL_ELO_OFFSET", DEFAULT_BOT_ELO_OFFSET))
    except ValueError:
        offset = DEFAULT_BOT_ELO_OFFSET
    return min(300, max(-600, offset))


def effective_bot_elo(profile: dict, elo_offset: int | None = None) -> int:
    """Return engine strength after applying the game-wide calibration."""
    offset = configured_bot_elo_offset() if elo_offset is None else elo_offset
    offset = min(300, max(-600, offset))
    return min(2800, max(600, int(profile["target_elo"]) + offset))


def opening_plan_moves(
    board: chess.Board, profile: dict
) -> list[tuple[chess.Move, int]]:
    """Find the next legal repertoire move while tolerating opponent deviations."""
    history = [move.uci() for move in board.move_stack]
    color = "white" if board.turn == chess.WHITE else "black"
    parity = 0 if board.turn == chess.WHITE else 1
    played_by_bot = history[parity::2]
    planned = []
    for preference in profile.get("openings", []):
        if preference["color"] != color:
            continue
        opening = find_opening(preference["opening_id"])
        line = opening.get("uci", []) if opening else []
        own_line = line[parity::2]
        if not own_line or own_line[: len(played_by_bot)] != played_by_bot:
            continue
        # Black openings depend on White's first move (e.g. a Sicilian needs 1.e4).
        if parity == 1 and not played_by_bot and (not history or history[0] != line[0]):
            continue
        if len(own_line) <= len(played_by_bot):
            continue
        move = chess.Move.from_uci(own_line[len(played_by_bot)])
        if move in board.legal_moves:
            planned.append((move, max(1, preference.get("weight", 50))))
    return planned


def opening_repertoire_status(
    board: chess.Board, profile: dict, bot_color: chess.Color
) -> str:
    """Return whether the game is still in, completed, or left a favorite line."""
    color = "white" if bot_color == chess.WHITE else "black"
    history = [move.uci() for move in board.move_stack]
    lines = []
    for preference in profile.get("openings", []):
        if preference.get("color") != color:
            continue
        opening = find_opening(preference.get("opening_id", ""))
        line = opening.get("uci", []) if opening else []
        if line:
            lines.append(line)
    if not lines:
        return "none"
    if any(
        len(history) < len(line) and history == line[: len(history)]
        for line in lines
    ):
        return "active"
    if any(
        len(history) >= len(line) and history[: len(line)] == line
        for line in lines
    ):
        return "completed"
    return "deviated"


def favorite_opening_names(profile: dict, bot_color: chess.Color) -> list[str]:
    color = "white" if bot_color == chess.WHITE else "black"
    names = []
    for preference in profile.get("openings", []):
        if preference.get("color") != color:
            continue
        opening = find_opening(preference.get("opening_id", ""))
        name = (opening or {}).get("name") or preference.get("name")
        if name and name not in names:
            names.append(name)
    return names


def san_move_history(board: chess.Board) -> list[str]:
    replay = board.root()
    result = []
    for move in board.move_stack:
        result.append(replay.san(move))
        replay.push(move)
    return result


async def choose_bot_move(
    board: chess.Board,
    profile: dict,
    rng: random.Random | None = None,
    elo_offset: int | None = None,
) -> chess.Move:
    rng = rng or random.Random()
    planned_moves = opening_plan_moves(board, profile)
    effective_elo = effective_bot_elo(profile, elo_offset)
    extra_weakening = bool(profile.get("extra_weakening", False))

    engine_path = os.getenv("STOCKFISH_PATH")
    if not engine_path or not os.path.exists(engine_path):
        raise FileNotFoundError(
            f"Nie znaleziono silnika pod ścieżką: {engine_path}. Sprawdź plik .env."
        )
    _, engine = await chess.engine.popen_uci(engine_path)
    try:
        await engine.configure(
            {
                "UCI_LimitStrength": True,
                "UCI_Elo": max(STOCKFISH_MIN_UCI_ELO, effective_elo),
            }
        )
        legal_count = board.legal_moves.count()
        multipv = min(20 if extra_weakening else 12, legal_count)
        think_time = 0.12 + ((effective_elo - 800) / 2000) * 0.45
        infos = await engine.analyse(
            board, chess.engine.Limit(time=think_time), multipv=multipv
        )
    finally:
        await engine.quit()

    candidates = []
    best_score = None
    for info in infos:
        variation = info.get("pv")
        score_obj = info.get("score")
        if not variation or score_obj is None:
            continue
        move = variation[0]
        score = score_obj.pov(board.turn).score(mate_score=100000)
        if score is None:
            continue
        best_score = score if best_score is None else max(best_score, score)
        candidates.append((move, score))
    if not candidates:
        return rng.choice(list(board.legal_moves))

    elo_ratio = (effective_elo - 800) / 2000
    weakness = min(1.1, max(0.0, 1 - elo_ratio))
    max_loss = 200 * (1 - elo_ratio) ** 1.5 + 30
    if extra_weakening:
        max_loss += 450 * weakness**1.5
    viable = [
        (move, score) for move, score in candidates if best_score - score <= max_loss
    ]
    style = profile["style"]
    temperature = max(8, 12 + 35 * (1 - elo_ratio) + style["risk"] * 0.35)
    if extra_weakening:
        temperature += 80 * weakness

    # Continue the opening plan only if Stockfish still considers it sound.
    viable_moves = {move for move, _ in viable}
    safe_planned = [
        (move, weight) for move, weight in planned_moves if move in viable_moves
    ]
    opening_adherence = 0.55 + 0.35 * min(1.0, max(0.0, elo_ratio))
    if safe_planned and (
        not extra_weakening or rng.random() < opening_adherence
    ):
        return rng.choices(
            [move for move, _ in safe_planned],
            weights=[weight for _, weight in safe_planned],
            k=1,
        )[0]

    utilities = []
    for move, score in viable:
        capture = board.is_capture(move)
        captured_piece = board.piece_at(move.to_square)
        captured_value = (
            PIECE_VALUES.get(captured_piece.piece_type, 0) if captured_piece else 0
        )
        trial = board.copy(stack=False)
        trial.push(move)
        gives_check = trial.is_check()
        style_bonus = (style["aggression"] - 50) * (8 if gives_check else 0) / 50
        style_bonus += (
            (style["tacticality"] - 50) * (5 if capture or gives_check else 0) / 50
        )
        style_bonus += (style["materialism"] - 50) * captured_value * 3 / 50
        style_bonus += (style["simplification"] - 50) * (4 if capture else 0) / 50
        utilities.append((move, score + style_bonus))
    peak = max(value for _, value in utilities)
    weights = [math.exp((value - peak) / temperature) for _, value in utilities]
    return rng.choices([move for move, _ in utilities], weights=weights, k=1)[0]


async def detect_commentary_event(board: chess.Board, move: chess.Move) -> dict | None:
    """Use a quick engine pass to decide whether a player's move merits a comment."""
    engine_path = os.getenv("STOCKFISH_PATH")
    if not engine_path or not os.path.exists(engine_path):
        return None

    mover = board.turn
    played_san = board.san(move)
    was_capture = board.is_capture(move)
    _, engine = await chess.engine.popen_uci(engine_path)
    try:
        before = await engine.analyse(board, chess.engine.Limit(time=0.18))
        best_move = before.get("pv", [None])[0]
        best_san = board.san(best_move) if best_move else None
        best_line_san = []
        line_board = board.copy(stack=False)
        for line_move in before.get("pv", [])[:5]:
            if line_move not in line_board.legal_moves:
                break
            best_line_san.append(line_board.san(line_move))
            line_board.push(line_move)
        before_score_obj = before.get("score")
        if before_score_obj is None:
            return None
        before_score = before_score_obj.pov(mover).score(mate_score=100000)

        after_board = board.copy(stack=True)
        after_board.push(move)
        after = await engine.analyse(after_board, chess.engine.Limit(time=0.18))
        raw_after_score = after.get("score")
        if raw_after_score is None:
            return None
        after_score_obj = raw_after_score.pov(mover)
        after_score = after_score_obj.score(mate_score=100000)
    finally:
        await engine.quit()

    if before_score is None or after_score is None:
        return None
    loss = max(0, before_score - after_score)
    gives_check = after_board.is_check()

    if after_score_obj.is_mate() and (after_score_obj.mate() or 0) < 0:
        kind = "przeoczony lub nieunikniony mat"
    elif loss >= 160:
        kind = "poważny blunder"
    elif loss >= 70:
        kind = "istotne przeoczenie"
    elif best_move == move and len(board.move_stack) >= 8:
        kind = (
            "bardzo dobry ruch taktyczny lub kombinacja"
            if was_capture or gives_check
            else "bardzo dobry ruch pozycyjny"
        )
    else:
        return None

    return {
        "type": kind,
        "played_move_san": played_san,
        "best_move_san": best_san,
        "best_line_san": best_line_san,
        "evaluation_loss_pawns": round(loss / 100, 1),
        "gave_check": gives_check,
        "was_capture": was_capture,
    }


@dataclass
class BotGame:
    bot: dict
    player_color: chess.Color
    elo_offset: int | None = None
    board: chess.Board = field(default_factory=chess.Board)
    status: str = "active"
    result: str | None = None
    last_move_uci: str | None = None
    bot_message: str | None = None
    llm_commentary_enabled: bool = False
    llm_commentary: str | None = None
    last_comment_ply: int = -10
    opening_repertoire_active: bool = False
    last_commentary_usage: dict = field(default_factory=dict)

    @property
    def bot_color(self):
        return not self.player_color

    def finish_if_needed(self):
        outcome = self.board.outcome(claim_draw=True)
        if not outcome:
            return False
        self.status = outcome.termination.name.lower()
        self.result = outcome.result()
        bot_won = outcome.winner is self.bot_color
        self.bot_message = self.bot["phrases"]["victory" if bot_won else "defeat"]
        return True

    def pgn(self):
        game = chess.pgn.Game.from_board(self.board)
        game.headers["Event"] = "Rajko Chess Bot Game"
        game.headers["White"] = (
            "Gracz" if self.player_color == chess.WHITE else self.bot["name"]
        )
        game.headers["Black"] = (
            "Gracz" if self.player_color == chess.BLACK else self.bot["name"]
        )
        game.headers["Result"] = self.result or "*"
        return str(game)

    def response(self):
        return {
            "fen": self.board.fen(),
            "history": [move.uci() for move in self.board.move_stack],
            "player_color": "white" if self.player_color else "black",
            "bot": self.bot,
            "turn": "white" if self.board.turn else "black",
            "status": self.status,
            "result": self.result,
            "last_move_uci": self.last_move_uci,
            "bot_message": self.bot_message,
            "pgn": self.pgn() if self.status != "active" else None,
            "llm_commentary_enabled": self.llm_commentary_enabled,
            "llm_commentary": self.llm_commentary,
        }


class BotGameManager:
    def __init__(self):
        self.games: dict[str, BotGame] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    def lock(self, session_id):
        return self.locks.setdefault(session_id, asyncio.Lock())

    async def start(
        self,
        session_id,
        bot,
        player_color,
        llm_commentary=False,
        elo_offset: int | None = None,
    ):
        color = (
            random.choice([chess.WHITE, chess.BLACK])
            if player_color == "random"
            else player_color == "white"
        )
        game = BotGame(
            bot=bot,
            player_color=color,
            elo_offset=elo_offset,
            bot_message=None if llm_commentary else bot["phrases"]["greeting"],
            llm_commentary_enabled=llm_commentary,
        )
        game.opening_repertoire_active = (
            opening_repertoire_status(game.board, bot, game.bot_color) == "active"
        )
        self.games[session_id] = game
        opening_event = None
        if game.board.turn == game.bot_color:
            opening_event = await self._bot_turn(game)
        if game.llm_commentary_enabled:
            greeting = await generate_bot_game_greeting(
                bot=game.bot,
                positions={"current": game.board.fen()},
                move_history_san=san_move_history(game.board),
                opening_event=opening_event,
            )
            if greeting:
                game.llm_commentary = greeting.text
                game.last_commentary_usage = greeting.usage
            else:
                game.bot_message = bot["phrases"]["greeting"]
        return game.response()

    def take_commentary_usage(self, session_id: str) -> dict:
        game = self.games.get(session_id)
        if not game:
            return {}
        usage = game.last_commentary_usage
        game.last_commentary_usage = {}
        return usage

    @staticmethod
    def _opening_deviation_event(game: BotGame) -> dict | None:
        if not game.opening_repertoire_active:
            return None
        status = opening_repertoire_status(game.board, game.bot, game.bot_color)
        if status == "active":
            return None
        game.opening_repertoire_active = False
        if status != "deviated":
            return None
        return {
            "type": "left_favorite_opening",
            "preferred_openings": favorite_opening_names(game.bot, game.bot_color),
            "reason": "Historia ruchów przestała pasować do ulubionych linii bota.",
        }

    async def move(self, session_id, uci):
        game = self.games.get(session_id)
        if not game or game.status != "active":
            raise ValueError("Brak aktywnej partii")
        if game.board.turn != game.player_color:
            raise ValueError("Teraz ruch bota")
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise ValueError("Nieprawidłowy ruch") from exc
        if move not in game.board.legal_moves:
            raise ValueError("Nielegalny ruch")
        commentary_event = None
        position_before_player_move = game.board.fen()
        if (
            game.llm_commentary_enabled
            and len(game.board.move_stack) - game.last_comment_ply >= 4
        ):
            try:
                commentary_event = await detect_commentary_event(game.board, move)
            except Exception:  # noqa: BLE001 - optional commentary must not break moves
                # Dodatkowa analiza komentarza nie może zablokować legalnego ruchu.
                commentary_event = None
        captured = game.board.piece_at(move.to_square)
        game.board.push(move)
        position_after_player_move = game.board.fen()
        opening_event = (
            self._opening_deviation_event(game)
            if game.llm_commentary_enabled
            else None
        )
        game.last_move_uci = move.uci()
        game.bot_message = (
            game.bot["phrases"]["setback"]
            if (
                game.board.is_check()
                or (captured and PIECE_VALUES[captured.piece_type] >= 5)
            )
            else None
        )
        if not game.finish_if_needed():
            bot_opening_event = await self._bot_turn(game)
            opening_event = opening_event or bot_opening_event
        game.llm_commentary = None
        game.last_commentary_usage = {}
        selected_event = opening_event or commentary_event
        if selected_event:
            commentary = await generate_bot_move_commentary(
                bot=game.bot,
                event=selected_event,
                positions={
                    "before_player_move": position_before_player_move,
                    "after_player_move": position_after_player_move,
                    "current_after_bot_reply": game.board.fen(),
                },
                move_history_san=san_move_history(game.board),
            )
            if commentary:
                game.llm_commentary = commentary.text
                game.last_commentary_usage = commentary.usage
                game.last_comment_ply = len(game.board.move_stack)
        return game.response()

    async def _bot_turn(self, game):
        started_at = time.monotonic()
        move = await choose_bot_move(
            game.board, game.bot, elo_offset=game.elo_offset
        )
        # Ruchy z książki i łatwe pozycje nie powinny pojawiać się natychmiast.
        # Czas obejmuje analizę silnika, więc opóźniamy tylko brakującą część.
        desired_think_time = random.uniform(0.55, 1.15)
        await asyncio.sleep(
            max(0, desired_think_time - (time.monotonic() - started_at))
        )
        captured = game.board.piece_at(move.to_square)
        game.board.push(move)
        opening_event = (
            self._opening_deviation_event(game)
            if game.llm_commentary_enabled
            else None
        )
        game.last_move_uci = move.uci()
        if game.board.is_check() or (
            captured and PIECE_VALUES[captured.piece_type] >= 5
        ):
            game.bot_message = game.bot["phrases"]["advantage"]
        game.finish_if_needed()
        return opening_event

    def resign(self, session_id):
        game = self.games.get(session_id)
        if not game or game.status != "active":
            raise ValueError("Brak aktywnej partii")
        game.status = "resigned"
        game.result = "0-1" if game.player_color == chess.WHITE else "1-0"
        game.bot_message = game.bot["phrases"]["victory"]
        return game.response()

    def draw_offer(self, session_id):
        game = self.games.get(session_id)
        if not game or game.status != "active":
            raise ValueError("Brak aktywnej partii")
        material = sum(
            len(game.board.pieces(piece, color)) * value
            for piece, value in PIECE_VALUES.items()
            for color in [chess.WHITE, chess.BLACK]
        )
        accepted = len(game.board.move_stack) >= 40 and (
            material <= 20 or game.bot["style"]["simplification"] >= 70
        )
        game.bot_message = game.bot["phrases"]["draw_offer"]
        if accepted:
            game.status, game.result = "draw_agreement", "1/2-1/2"
        return {**game.response(), "draw_accepted": accepted}
