# chess_logic/game.py
import chess

class ChessGame:
    def __init__(self):
        self.board = chess.Board()

    def get_fen(self) -> str:
        """Zwraca obecną pozycję w formacie FEN."""
        return self.board.fen()

    def make_move(self, uci_move: str) -> bool:
        """Próbuje wykonać ruch w formacie UCI. Zwraca True jeśli się powiodło."""
        try:
            move = chess.Move.from_uci(uci_move)
            if move in self.board.legal_moves:
                self.board.push(move)
                return True
            return False
        except ValueError:
            # Rzucane, gdy ciąg znaków nie jest prawidłowym ruchem UCI
            return False

    def undo_move(self) -> bool:
        """Cofa ostatni ruch. Zwraca True jeśli cofnięto, False jeśli brak ruchów."""
        if len(self.board.move_stack) > 0:
            self.board.pop()
            return True
        return False

    def get_history(self) -> list[str]:
        """Zwraca listę wykonanych ruchów w formacie UCI."""
        return [move.uci() for move in self.board.move_stack]

    def reset(self):
        """Resetuje szachownicę do pozycji startowej."""
        self.board.reset()


