# chess_logic/game.py
from io import StringIO

import chess
import chess.pgn

class ChessGame:
    def __init__(self):
        self.board = chess.Board()
        self.imported_pgn = None
        self.imported_metadata = None
        self.imported_moves = []
        self.current_ply = 0
        self.in_variation = False

    def get_fen(self) -> str:
        """Zwraca obecną pozycję w formacie FEN."""
        return self.board.fen()

    def make_move(self, uci_move: str, preserve_imported_context: bool = False) -> bool:
        """Próbuje wykonać ruch w formacie UCI. Zwraca True jeśli się powiodło."""
        try:
            move = chess.Move.from_uci(uci_move)
            if move in self.board.legal_moves:
                self.board.push(move)
                if preserve_imported_context and self.imported_pgn:
                    self.in_variation = True
                else:
                    self.imported_pgn = None
                    self.imported_metadata = None
                    self.imported_moves = []
                    self.current_ply = 0
                    self.in_variation = False
                return True
            return False
        except ValueError:
            # Rzucane, gdy ciąg znaków nie jest prawidłowym ruchem UCI
            return False

    def undo_move(self, preserve_imported_context: bool = False) -> bool:
        """Cofa ostatni ruch. Zwraca True jeśli cofnięto, False jeśli brak ruchów."""
        if len(self.board.move_stack) > 0:
            self.board.pop()
            if preserve_imported_context and self.imported_pgn:
                self.in_variation = len(self.board.move_stack) > self.current_ply
            else:
                self.imported_pgn = None
                self.imported_metadata = None
                self.imported_moves = []
                self.current_ply = 0
                self.in_variation = False
            return True
        return False

    def get_history(self) -> list[str]:
        """Zwraca listę wykonanych ruchów w formacie UCI."""
        return [move.uci() for move in self.board.move_stack]

    def get_ancestor_fens(self, limit: int = 30) -> list[str]:
        """Returns earlier positions, starting with the position before the last move."""
        board = self.board.copy(stack=True)
        ancestor_fens = []

        while board.move_stack and len(ancestor_fens) < limit:
            board.pop()
            ancestor_fens.append(board.fen())

        return ancestor_fens

    def reset(self):
        """Resetuje szachownicę do pozycji startowej."""
        self.board.reset()
        self.imported_pgn = None
        self.imported_metadata = None
        self.imported_moves = []
        self.current_ply = 0
        self.in_variation = False

    def load_pgn(self, pgn: str, metadata: dict | None = None) -> dict:
        """Loads a completed PGN and sets the board to its final position."""
        parsed_game = chess.pgn.read_game(StringIO(pgn))
        if parsed_game is None:
            raise ValueError("Nie udało się odczytać zapisu PGN")

        board = parsed_game.board()
        moves = list(parsed_game.mainline_moves())
        for move in moves:
            board.push(move)

        self.board = board
        self.imported_pgn = pgn
        self.imported_metadata = metadata or {}
        self.imported_moves = moves
        self.current_ply = len(moves)
        self.in_variation = False

        return self._imported_position_response(dict(parsed_game.headers))

    def go_to_imported_ply(self, ply: int) -> dict:
        """Moves the imported game review board to the requested half-move."""
        if not self.imported_pgn:
            raise ValueError("Najpierw zaimportuj zakończoną partię")

        previous_ply = self.current_ply
        target_ply = min(max(ply, 0), len(self.imported_moves))
        parsed_game = chess.pgn.read_game(StringIO(self.imported_pgn))
        if parsed_game is None:
            raise ValueError("Nie udało się odczytać zapisu PGN")

        board = parsed_game.board()
        for move in self.imported_moves[:target_ply]:
            board.push(move)

        self.board = board
        self.current_ply = target_ply
        self.in_variation = False
        navigation_move = None
        if target_ply > previous_ply:
            navigation_move = self.imported_moves[target_ply - 1]
        elif target_ply < previous_ply and target_ply != 0:
            navigation_move = self.imported_moves[previous_ply - 1]

        return self._imported_position_response(
            dict(parsed_game.headers),
            navigation_move=navigation_move,
        )

    def _imported_position_response(
        self,
        headers: dict,
        navigation_move: chess.Move | None = None,
    ) -> dict:
        last_move_san = None
        move_label = "Pozycja startowa"
        if self.current_ply:
            previous_board = self.board.copy()
            last_move = previous_board.pop()
            last_move_san = previous_board.san(last_move)
            move_number = (self.current_ply + 1) // 2
            move_label = (
                f"{move_number}. {last_move_san}"
                if self.current_ply % 2 else f"{move_number}... {last_move_san}"
            )

        return {
            "fen": self.get_fen(),
            "history": self.get_history(),
            "headers": headers,
            "metadata": self.imported_metadata,
            "current_ply": self.current_ply,
            "total_plies": len(self.imported_moves),
            "in_variation": self.in_variation,
            "variation_ply_count": max(0, len(self.board.move_stack) - self.current_ply) if self.imported_pgn else 0,
            "move_label": move_label,
            "last_move_san": last_move_san,
            "navigation_move_uci": navigation_move.uci() if navigation_move else None,
        }

    def get_imported_game(self) -> dict | None:
        if not self.imported_pgn:
            return None
        return {
            "pgn": self.imported_pgn,
            "metadata": self.imported_metadata or {},
        }
