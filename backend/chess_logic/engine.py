import os
import chess
import chess.engine


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