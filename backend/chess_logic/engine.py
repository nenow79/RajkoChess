import os
import chess
import chess.engine
import chess.pgn
from io import StringIO


async def analyze_position(fen: str, time_limit: float = 0.5, multipv: int = 3) -> dict:
    stockfish_path = os.getenv("STOCKFISH_PATH")

    if not stockfish_path or not os.path.exists(stockfish_path):
        raise FileNotFoundError(f"Nie znaleziono silnika pod ścieżką: {stockfish_path}. Sprawdź plik .env.")

    board = chess.Board(fen)
    transport, engine = await chess.engine.popen_uci(stockfish_path)

    try:
        infos = await engine.analyse(
            board,
            chess.engine.Limit(time=time_limit),
            multipv=multipv
        )

        variations = []
        for info in infos:
            score_obj = info["score"].white()
            is_mate = score_obj.is_mate()

            if is_mate:
                value = score_obj.mate()
                eval_text = f"#{value}"
            else:
                value = round(score_obj.score() / 100.0, 2)
                eval_text = f"{value:.2f}"

            # Zmienne na najlepszy ruch
            best_move_uci = None
            best_move_san = None

            if "pv" in info and info["pv"]:
                best_move = info["pv"][0]
                best_move_uci = best_move.uci()
                # Tłumaczenie pierwszego ruchu na SAN
                best_move_san = board.san(best_move)

            # Generowanie wariantu (linii)
            line_uci = []
            line_san = []

            # Tworzymy kopię planszy, aby symulować ruchy wariantu
            # Nie chcemy modyfikować oryginalnej planszy 'board'
            temp_board = board.copy()

            for move in info.get("pv", [])[:4]:
                line_uci.append(move.uci())
                # Generujemy SAN przed wykonaniem ruchu
                line_san.append(temp_board.san(move))
                # Wykonujemy ruch na kopii, aby kolejny ruch w pętli miał poprawny kontekst dla SAN
                temp_board.push(move)

            variations.append({
                "is_mate": is_mate,
                "score": value,
                "evaluation": eval_text,
                "best_move_uci": best_move_uci,
                "best_move_san": best_move_san,  # Dodane: np. "Nf3"
                "depth": info.get("depth", 0),
                "line_uci": line_uci,
                "line_san": line_san  # Dodane: np. ["Nf3", "d6", "Bc4", "Nf6"]
            })

        return {
            "fen": fen,
            "variations": variations
        }
    finally:
        await engine.quit()


async def analyze_game(pgn: str, time_limit: float = 0.15, critical_count: int = 8) -> dict:
    """Analyzes every played move and returns the largest evaluation losses."""
    stockfish_path = os.getenv("STOCKFISH_PATH")
    if not stockfish_path or not os.path.exists(stockfish_path):
        raise FileNotFoundError(f"Nie znaleziono silnika pod ścieżką: {stockfish_path}. Sprawdź plik .env.")

    parsed_game = chess.pgn.read_game(StringIO(pgn))
    if parsed_game is None:
        raise ValueError("Nie udało się odczytać zapisu PGN")

    board = parsed_game.board()
    transport, engine = await chess.engine.popen_uci(stockfish_path)
    moments = []

    try:
        before_info = await engine.analyse(board, chess.engine.Limit(time=time_limit))
        before_score = _score_for_white(before_info)

        for ply, move in enumerate(parsed_game.mainline_moves(), start=1):
            mover = "white" if board.turn == chess.WHITE else "black"
            played_san = board.san(move)
            best_move = before_info.get("pv", [None])[0]
            best_move_san = board.san(best_move) if best_move else None
            best_line_san = _line_to_san(board, before_info.get("pv", [])[:4])

            board.push(move)
            after_info = await engine.analyse(board, chess.engine.Limit(time=time_limit))
            after_score = _score_for_white(after_info)
            loss = before_score - after_score if mover == "white" else after_score - before_score

            moments.append({
                "ply": ply,
                "move_number": (ply + 1) // 2,
                "color": mover,
                "played": played_san,
                "best_move": best_move_san,
                "best_line": best_line_san,
                "evaluation_before": round(before_score, 2),
                "evaluation_after": round(after_score, 2),
                "loss": round(max(loss, 0), 2),
                "fen_after": board.fen(),
            })
            before_info = after_info
            before_score = after_score
    finally:
        await engine.quit()

    critical = sorted(moments, key=lambda item: item["loss"], reverse=True)[:critical_count]
    return {
        "headers": dict(parsed_game.headers),
        "move_count": len(moments),
        "final_fen": board.fen(),
        "critical_moments": critical,
    }


def _score_for_white(info: dict) -> float:
    return info["score"].white().score(mate_score=100000) / 100.0


def _line_to_san(board: chess.Board, moves: list[chess.Move]) -> list[str]:
    temp_board = board.copy()
    line = []
    for move in moves:
        if move not in temp_board.legal_moves:
            break
        line.append(temp_board.san(move))
        temp_board.push(move)
    return line
