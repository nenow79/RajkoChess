import unittest

from chess_logic.game import ChessGame


class ImportedPositionTests(unittest.TestCase):
    def test_position_state_includes_active_imported_game_context(self):
        game = ChessGame()
        loaded = game.load_pgn(
            "1. e4 e5 2. Nf3 *",
            {"source": "chesscom", "opponent": "Tester"},
            game_id="saved-game",
        )
        game.go_to_imported_ply(2)

        response = game.get_position_state()

        self.assertEqual(response["game_id"], "saved-game")
        self.assertEqual(response["metadata"]["opponent"], "Tester")
        self.assertEqual(response["pgn"], "1. e4 e5 2. Nf3 *")
        self.assertEqual(response["current_ply"], 2)
        self.assertEqual(response["total_plies"], loaded["total_plies"])

    def test_position_state_without_import_contains_only_fen(self):
        response = ChessGame().get_position_state()

        self.assertEqual(set(response), {"fen"})

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
