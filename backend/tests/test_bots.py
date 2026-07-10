import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chess

from chess_logic.bot_game import BotGameManager
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
