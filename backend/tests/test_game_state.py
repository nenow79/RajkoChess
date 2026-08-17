import unittest

from chess_logic.game import ChessGame


class ImportedPositionTests(unittest.TestCase):
    def test_valid_fen_replaces_board_and_clears_imported_game(self):
        game = ChessGame()
        game.load_pgn("1. e4 e5 *", {"source": "pgn"}, game_id="saved-game")

        response = game.load_fen("8/8/8/8/8/8/7k/K7 w - - 0 1")

        self.assertEqual(response["fen"], "8/8/8/8/8/8/7k/K7 w - - 0 1")
        self.assertIsNone(game.get_imported_game())

    def test_invalid_fen_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "FEN"):
            ChessGame().load_fen("to nie jest FEN")


if __name__ == "__main__":
    unittest.main()
