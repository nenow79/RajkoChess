import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chess

from chess_logic.bot_game import BotGameManager, choose_bot_move, opening_plan_moves
from chess_logic.bots import BotStore
from chess_logic.openings import search_openings


class BotStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = BotStore(str(Path(self.tempdir.name) / "bots.sqlite3"))

    def tearDown(self):
        self.tempdir.cleanup()

    def test_seeds_and_crud(self):
        self.assertEqual(len(self.store.list()), 3)
        profile = {
            "name": "Testowy", "description": "Bot do testów", "avatar": "🧪", "target_elo": 50,
            "style": {"aggression": 999}, "openings": [], "phrases": {},
        }
        created = self.store.create(profile)
        self.assertEqual(created["target_elo"], 800)
        self.assertEqual(created["style"]["aggression"], 100)
        created["name"] = "Zmieniony"
        self.assertEqual(self.store.update(created["id"], created)["name"], "Zmieniony")
        self.assertTrue(self.store.delete(created["id"]))
        self.assertIsNone(self.store.get(created["id"]))

    def test_opening_catalog_is_searchable(self):
        matches = search_openings("Sicilian Defense", 5)
        self.assertTrue(matches)
        self.assertTrue(all(item["uci"] for item in matches))


class BotGameTests(unittest.IsolatedAsyncioTestCase):
    def test_opening_plan_survives_opponent_deviation(self):
        board = chess.Board()
        for uci in ("d2d4", "g8f6", "g1f3", "d7d6"):
            board.push_uci(uci)
        london = search_openings("London System", 1)[0]
        profile = {"openings": [{"opening_id": london["id"], "color": "white", "weight": 100}]}
        self.assertEqual(opening_plan_moves(board, profile), [(chess.Move.from_uci("c1f4"), 100)])

    def test_black_opening_requires_matching_first_move(self):
        board = chess.Board()
        board.push_uci("d2d4")
        sicilian = search_openings("Sicilian Defense", 1)[0]
        profile = {"openings": [{"opening_id": sicilian["id"], "color": "black", "weight": 100}]}
        self.assertEqual(opening_plan_moves(board, profile), [])

    async def test_low_elo_bot_still_chooses_an_engine_candidate(self):
        board = chess.Board()
        profile = {"target_elo": 800, "openings": [], "style": {
            "aggression": 50, "tacticality": 50, "risk": 50,
            "materialism": 50, "simplification": 50,
        }}
        candidate = chess.Move.from_uci("e2e4")
        engine = unittest.mock.AsyncMock()
        engine.analyse.return_value = [{"pv": [candidate], "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE)}]
        engine.quit = unittest.mock.AsyncMock()
        with patch("chess_logic.bot_game.os.path.exists", return_value=True), \
                patch("chess_logic.bot_game.os.getenv", return_value="/stockfish"), \
                patch("chess_logic.bot_game.chess.engine.popen_uci", return_value=(None, engine)):
            move = await choose_bot_move(board, profile)
        self.assertEqual(move, candidate)

    async def test_player_and_bot_moves_are_atomic_and_sanitized(self):
        store_dir = tempfile.TemporaryDirectory()
        try:
            bot = BotStore(str(Path(store_dir.name) / "bots.sqlite3")).list()[0]
            manager = BotGameManager()

            async def fake_move(board, profile, rng=None):
                self.assertEqual(profile["id"], bot["id"])
                return chess.Move.from_uci("e7e5")

            with patch("chess_logic.bot_game.choose_bot_move", fake_move):
                started = await manager.start("session", bot, "white")
                self.assertEqual(started["history"], [])
                response = await manager.move("session", "e2e4")
            self.assertEqual(response["history"], ["e2e4", "e7e5"])
            self.assertNotIn("evaluation", response)
            self.assertNotIn("variations", response)
            resigned = manager.resign("session")
            self.assertEqual(resigned["result"], "0-1")
            self.assertIn("Rajko Chess Bot Game", resigned["pgn"])
        finally:
            store_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
