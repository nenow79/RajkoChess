import os
import re
from io import StringIO

import chess
import chess.engine
import chess.pgn


PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

POLISH_SAN_PIECES = {"Q": "H", "R": "W", "B": "G", "N": "S"}


def find_legal_move_in_text(fen: str, text: str) -> str | None:
    """Return one unambiguously mentioned legal move as UCI.

    Both standard SAN/UCI and the common Polish piece initials H/W/G/S are
    accepted. When a question mentions multiple legal moves, no candidate is
    selected automatically; the normal MultiPV analysis still applies.
    """
    board = chess.Board(fen)
    found: set[str] = set()
    normalized_text = " ".join(text.casefold().split())
    castling_moves = [move for move in board.legal_moves if board.is_castling(move)]
    long_castle = bool(
        re.search(r"(?:dług[ąa]\s+roszad|roszad\w*\s+dług|long\s+castl|queenside\s+castl)", normalized_text)
    )
    short_castle = bool(
        re.search(r"(?:krótk[ąa]\s+roszad|roszad\w*\s+krótk|short\s+castl|kingside\s+castl)", normalized_text)
    )
    mentions_castling = bool(re.search(r"\broszad\w*|\bcastl\w*", normalized_text))
    if long_castle or short_castle or mentions_castling:
        matching_castles = castling_moves
        if long_castle and not short_castle:
            matching_castles = [
                move for move in castling_moves if move.to_square < move.from_square
            ]
        elif short_castle and not long_castle:
            matching_castles = [
                move for move in castling_moves if move.to_square > move.from_square
            ]
        if len(matching_castles) == 1:
            found.add(matching_castles[0].uci())

    for move in board.legal_moves:
        san = board.san(move)
        aliases = {san, san.rstrip("+#"), move.uci()}
        if san.startswith(tuple(POLISH_SAN_PIECES)):
            polish = POLISH_SAN_PIECES[san[0]] + san[1:]
            aliases.update({polish, polish.rstrip("+#")})
        if san.startswith("O-O"):
            aliases.update({san.replace("O", "0"), san.rstrip("+#").replace("O", "0")})
        for alias in aliases:
            if re.search(
                rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])",
                text,
                re.IGNORECASE,
            ):
                found.add(move.uci())
                break
    return next(iter(found)) if len(found) == 1 else None


async def analyze_position(
    fen: str,
    time_limit: float = 0.5,
    multipv: int = 3,
    requested_move_uci: str | None = None,
) -> dict:
    stockfish_path = os.getenv("STOCKFISH_PATH")

    if not stockfish_path or not os.path.exists(stockfish_path):
        raise FileNotFoundError(
            f"Nie znaleziono silnika pod ścieżką: {stockfish_path}. Sprawdź plik .env."
        )

    board = chess.Board(fen)
    _transport, engine = await chess.engine.popen_uci(stockfish_path)

    try:
        infos = await engine.analyse(
            board, chess.engine.Limit(time=time_limit), multipv=multipv
        )

        variations = []
        for info in infos:
            raw_score = info.get("score")
            if raw_score is None:
                continue
            score_obj = raw_score.white()
            is_mate = score_obj.is_mate()

            if is_mate:
                value = score_obj.mate()
                eval_text = f"#{value}"
            else:
                centipawns = score_obj.score()
                if centipawns is None:
                    continue
                value = round(centipawns / 100.0, 2)
                eval_text = f"{value:.2f}"

            # Zmienne na najlepszy ruch
            best_move_uci = None
            best_move_san = None

            principal_variation = info.get("pv")
            if principal_variation:
                best_move = principal_variation[0]
                best_move_uci = best_move.uci()
                # Tłumaczenie pierwszego ruchu na SAN
                best_move_san = board.san(best_move)

            # Generowanie wariantu (linii)
            line_uci = []
            line_san = []

            # Tworzymy kopię planszy, aby symulować ruchy wariantu
            # Nie chcemy modyfikować oryginalnej planszy 'board'
            temp_board = board.copy()

            for move in (principal_variation or [])[:4]:
                line_uci.append(move.uci())
                # Generujemy SAN przed wykonaniem ruchu
                line_san.append(temp_board.san(move))
                # Wykonujemy ruch na kopii, aby kolejny ruch w pętli miał poprawny kontekst dla SAN
                temp_board.push(move)

            variations.append(
                {
                    "is_mate": is_mate,
                    "score": value,
                    "evaluation": eval_text,
                    "best_move_uci": best_move_uci,
                    "best_move_san": best_move_san,  # Dodane: np. "Nf3"
                    "depth": info.get("depth", 0),
                    "line_uci": line_uci,
                    "line_san": line_san,  # Dodane: np. ["Nf3", "d6", "Bc4", "Nf6"]
                    "evidence": _variation_evidence(
                        board, list(principal_variation or [])[:8]
                    ),
                }
            )

        requested_move = None
        if requested_move_uci:
            try:
                move = chess.Move.from_uci(requested_move_uci)
            except ValueError:
                move = None
            if move is not None and move in board.legal_moves and infos:
                mover = "white" if board.turn == chess.WHITE else "black"
                san = board.san(move)
                move_label = _move_label(board, san)
                before_score = _score_for_white(infos[0])
                after_board = board.copy()
                after_board.push(move)
                candidate_info = await engine.analyse(
                    board,
                    chess.engine.Limit(time=time_limit),
                    root_moves=[move],
                )
                after_score = _score_for_white(candidate_info)
                loss = (
                    before_score - after_score
                    if mover == "white"
                    else after_score - before_score
                )
                requested_move = {
                    "move_label": move_label,
                    "san": san,
                    "uci": move.uci(),
                    "color": mover,
                    "evaluation_before": round(before_score, 2),
                    "evaluation_after": round(after_score, 2),
                    "loss": round(max(loss, 0), 2),
                    "root_depth": infos[0].get("depth", 0),
                    "response_depth": candidate_info.get("depth", 0),
                    "move_facts": _played_move_facts(board, move, after_board),
                    "continuation": {
                        **_variation_evidence(
                            after_board,
                            list(candidate_info.get("pv", []))[1:9],
                            perspective=mover,
                        ),
                        "depth": candidate_info.get("depth", 0),
                    },
                }

        return {
            "fen": fen,
            "side_to_move": "white" if board.turn == chess.WHITE else "black",
            "variations": variations,
            "requested_move": requested_move,
        }
    finally:
        await engine.quit()


async def analyze_game(
    pgn: str,
    time_limit: float = 0.15,
    critical_count: int = 8,
    focus_color: str | None = None,
) -> dict:
    """Analyzes every played move and returns the largest evaluation losses."""
    stockfish_path = os.getenv("STOCKFISH_PATH")
    if not stockfish_path or not os.path.exists(stockfish_path):
        raise FileNotFoundError(
            f"Nie znaleziono silnika pod ścieżką: {stockfish_path}. Sprawdź plik .env."
        )

    parsed_game = chess.pgn.read_game(StringIO(pgn))
    if parsed_game is None:
        raise ValueError("Nie udało się odczytać zapisu PGN")

    board = parsed_game.board()
    _transport, engine = await chess.engine.popen_uci(stockfish_path)
    moments = []

    try:
        before_info = await engine.analyse(board, chess.engine.Limit(time=time_limit))
        before_score = _score_for_white(before_info)

        for ply, move in enumerate(parsed_game.mainline_moves(), start=1):
            mover = "white" if board.turn == chess.WHITE else "black"
            fen_before = board.fen()
            played_san = board.san(move)
            move_number = (ply + 1) // 2
            move_label = (
                f"{move_number}. {played_san}"
                if mover == "white"
                else f"{move_number}... {played_san}"
            )
            best_move = before_info.get("pv", [None])[0]
            best_move_san = board.san(best_move) if best_move else None
            best_line_san = _line_to_san(board, before_info.get("pv", [])[:4])

            board.push(move)
            after_info = await engine.analyse(
                board, chess.engine.Limit(time=time_limit)
            )
            after_score = _score_for_white(after_info)
            loss = (
                before_score - after_score
                if mover == "white"
                else after_score - before_score
            )

            moments.append(
                {
                    "ply": ply,
                    "move_number": move_number,
                    "move_label": move_label,
                    "color": mover,
                    "played": played_san,
                    "best_move": best_move_san,
                    "best_line": best_line_san,
                    "better_alternative": {
                        "move": best_move_san,
                        **_variation_evidence(
                            chess.Board(fen_before), before_info.get("pv", [])[:6]
                        ),
                    },
                    "punishment": _variation_evidence(
                        board, after_info.get("pv", [])[:8], perspective=mover
                    ),
                    "played_move_facts": _played_move_facts(
                        chess.Board(fen_before), move, board
                    ),
                    "side_to_move_after": "white" if board.turn else "black",
                    "evaluation_before": round(before_score, 2),
                    "evaluation_after": round(after_score, 2),
                    "loss": round(max(loss, 0), 2),
                    "fen_before": fen_before,
                    "fen_after": board.fen(),
                }
            )
            before_info = after_info
            before_score = after_score

        normalized_focus = focus_color if focus_color in {"white", "black"} else None
        candidates = (
            [moment for moment in moments if moment["color"] == normalized_focus]
            if normalized_focus
            else moments
        )
        critical = sorted(candidates, key=lambda item: item["loss"], reverse=True)[
            :critical_count
        ]

        # The first pass finds candidate mistakes cheaply. Re-check only those
        # positions more deeply so the coach receives a reliable alternative and
        # the concrete continuation that punishes the played move.
        second_pass_time = min(1.0, max(0.5, time_limit * 4))
        for moment in critical:
            before_board = chess.Board(moment["fen_before"])
            before_deep = await engine.analyse(
                before_board, chess.engine.Limit(time=second_pass_time)
            )
            before_pv = before_deep.get("pv", [])
            moment["best_move"] = (
                before_board.san(before_pv[0]) if before_pv else None
            )
            moment["best_line"] = _line_to_san(before_board, before_pv[:8])
            moment["better_alternative"] = {
                "move": moment["best_move"],
                **_variation_evidence(before_board, before_pv[:8]),
                "depth": before_deep.get("depth", 0),
            }

            after_board = chess.Board(moment["fen_after"])
            after_deep = await engine.analyse(
                after_board, chess.engine.Limit(time=second_pass_time)
            )
            deep_before_score = _score_for_white(before_deep)
            deep_after_score = _score_for_white(after_deep)
            deep_loss = (
                deep_before_score - deep_after_score
                if moment["color"] == "white"
                else deep_after_score - deep_before_score
            )
            moment["evaluation_before"] = round(deep_before_score, 2)
            moment["evaluation_after"] = round(deep_after_score, 2)
            moment["loss"] = round(max(deep_loss, 0), 2)
            moment["punishment"] = _variation_evidence(
                after_board,
                after_deep.get("pv", [])[:8],
                perspective=moment["color"],
            )
            moment["punishment"]["depth"] = after_deep.get("depth", 0)

        critical.sort(key=lambda item: item["loss"], reverse=True)

    finally:
        await engine.quit()

    evaluation_series = [
        {
            "ply": 0,
            "move_number": 0,
            "move_label": "Pozycja startowa",
            "evaluation": round(moments[0]["evaluation_before"], 2)
            if moments
            else round(before_score, 2),
        }
    ]
    evaluation_series.extend(
        {
            "ply": moment["ply"],
            "move_number": moment["move_number"],
            "move_label": (
                f"{moment['move_number']}. {moment['played']}"
                if moment["color"] == "white"
                else f"{moment['move_number']}... {moment['played']}"
            ),
            "evaluation": moment["evaluation_after"],
        }
        for moment in moments
    )

    return {
        "headers": dict(parsed_game.headers),
        "move_count": len(moments),
        "final_fen": board.fen(),
        "critical_moments": critical,
        "focus_color": normalized_focus,
        "evaluation_series": evaluation_series,
    }


def _score_for_white(info: chess.engine.InfoDict) -> float:
    score = info.get("score")
    if score is None:
        raise ValueError("Stockfish nie zwrócił oceny pozycji")
    centipawns = score.white().score(mate_score=100000)
    if centipawns is None:
        raise ValueError("Stockfish zwrócił pustą ocenę pozycji")
    return centipawns / 100.0


def _line_to_san(board: chess.Board, moves: list[chess.Move]) -> list[str]:
    temp_board = board.copy()
    line = []
    for move in moves:
        if move not in temp_board.legal_moves:
            break
        line.append(temp_board.san(move))
        temp_board.push(move)
    return line


def _piece_description(piece: chess.Piece, square: chess.Square) -> dict:
    return {
        "color": "white" if piece.color == chess.WHITE else "black",
        "piece": PIECE_NAMES[piece.piece_type],
        "square": chess.square_name(square),
        "value": PIECE_VALUES[piece.piece_type],
    }


def _captured_piece(board: chess.Board, move: chess.Move) -> tuple[chess.Piece, chess.Square] | None:
    if not board.is_capture(move):
        return None
    captured_square = move.to_square
    if board.is_en_passant(move):
        captured_square += -8 if board.turn == chess.WHITE else 8
    piece = board.piece_at(captured_square)
    return (piece, captured_square) if piece else None


def _material_balance_white(board: chess.Board) -> int:
    balance = 0
    for piece in board.piece_map().values():
        value = PIECE_VALUES[piece.piece_type]
        balance += value if piece.color == chess.WHITE else -value
    return balance


def _move_label(board: chess.Board, san: str) -> str:
    return (
        f"{board.fullmove_number}. {san}"
        if board.turn == chess.WHITE
        else f"{board.fullmove_number}... {san}"
    )


def _variation_evidence(
    board: chess.Board,
    moves: list[chess.Move],
    *,
    perspective: str | None = None,
) -> dict:
    """Return a legal, labelled engine line plus deterministic capture facts."""
    temp_board = board.copy()
    initial_balance = _material_balance_white(temp_board)
    line = []
    captures = []
    for move in moves:
        if move not in temp_board.legal_moves:
            break
        san = temp_board.san(move)
        label = _move_label(temp_board, san)
        captured = _captured_piece(temp_board, move)
        if captured:
            piece, square = captured
            captures.append(
                {
                    "move_label": label,
                    "captured": _piece_description(piece, square),
                }
            )
        line.append({"move_label": label, "san": san, "uci": move.uci()})
        temp_board.push(move)

    delta_white = _material_balance_white(temp_board) - initial_balance
    multiplier = -1 if perspective == "black" else 1
    return {
        "line": line,
        "captures": captures,
        "material_change_for_mover": (
            delta_white * multiplier if perspective in {"white", "black"} else None
        ),
    }


def _played_move_facts(
    before_board: chess.Board, move: chess.Move, after_board: chess.Board
) -> dict:
    moved_piece = before_board.piece_at(move.from_square)
    captured = _captured_piece(before_board, move)
    attacked_pieces = []
    piece_after = after_board.piece_at(move.to_square)
    if moved_piece and piece_after and piece_after.color == moved_piece.color:
        for square in sorted(after_board.attacks(move.to_square)):
            target = after_board.piece_at(square)
            if target and target.color != moved_piece.color:
                attacked_pieces.append(_piece_description(target, square))

    return {
        "moved_piece": (
            {
                **_piece_description(moved_piece, move.to_square),
                "from": chess.square_name(move.from_square),
                "to": chess.square_name(move.to_square),
            }
            if moved_piece
            else None
        ),
        "captured": _piece_description(*captured) if captured else None,
        "gives_check": after_board.is_check(),
        "directly_attacks_after_move": attacked_pieces,
    }
