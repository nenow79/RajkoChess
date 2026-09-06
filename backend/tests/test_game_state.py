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

    def test_reads_an_imported_position_without_moving_review_board(self):
        game = ChessGame()
        game.load_pgn("1. e4 e5 2. Nf3 *", {"source": "pgn"})
        original_fen = game.get_fen()

        position = game.get_imported_position_at_ply(1)

        self.assertEqual(position["ply"], 1)
        self.assertEqual(position["move_label"], "1. e4")
        self.assertEqual(position["history"], ["e2e4"])
        self.assertNotEqual(position["fen"], original_fen)
        self.assertEqual(game.get_fen(), original_fen)
        self.assertEqual(game.current_ply, 3)

    def test_rejects_a_position_beyond_the_imported_game(self):
        game = ChessGame()
        game.load_pgn("1. e4 e5 *", {"source": "pgn"})

        with self.assertRaisesRegex(ValueError, "nie istnieje"):
            game.get_imported_position_at_ply(3)


if __name__ == "__main__":
    unittest.main()
