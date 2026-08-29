import tempfile
import unittest
from os import environ
from pathlib import Path
from unittest.mock import AsyncMock, patch

import chess
import chess.engine
from chess_logic.bot_game import (
    BotGameManager,
    choose_bot_move,
    effective_bot_elo,
    opening_plan_moves,
    opening_repertoire_status,
)
from chess_logic.llm_agent import LLMResult
from chess_logic.runtime_settings import get_bot_global_elo_offset
from chess_logic.bots import BotStore
from chess_logic.openings import search_openings
from db.models import RuntimeSetting


class BotStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = BotStore(str(Path(self.tempdir.name) / "bots.sqlite3"))

    def tearDown(self):
        self.tempdir.cleanup()

    def test_seeds_and_crud(self):
        self.assertEqual(len(self.store.list()), 3)
        profile = {
            "name": "Testowy",
            "description": "Bot do testów",
            "avatar": "🧪",
            "target_elo": 50,
            "extra_weakening": True,
            "style": {"aggression": 999},
            "openings": [],
            "phrases": {},
        }
        created = self.store.create(profile)
        self.assertIsNotNone(created)
        assert created is not None
        self.assertEqual(created["target_elo"], 800)
        self.assertTrue(created["extra_weakening"])
        self.assertEqual(created["style"]["aggression"], 100)
        created["name"] = "Zmieniony"
        updated = self.store.update(created["id"], created)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["name"], "Zmieniony")
        self.assertTrue(self.store.delete(created["id"]))
        self.assertIsNone(self.store.get(created["id"]))

    def test_opening_catalog_is_searchable(self):
        matches = search_openings("Sicilian Defense", 5)
        self.assertTrue(matches)
        self.assertTrue(all(item["uci"] for item in matches))


class BotGameTests(unittest.IsolatedAsyncioTestCase):
    def test_global_elo_offset_defaults_to_minus_100_and_is_configurable(self):
        with patch.dict(environ, {}, clear=True):
            self.assertEqual(effective_bot_elo({"target_elo": 1500}), 1400)
        with patch.dict(environ, {"BOT_GLOBAL_ELO_OFFSET": "-250"}):
            self.assertEqual(effective_bot_elo({"target_elo": 1500}), 1250)

    async def test_database_elo_offset_overrides_environment(self):
        db = AsyncMock()
        db.get.return_value = RuntimeSetting(
            key="bot_global_elo_offset", value={"offset": -180}
        )

        self.assertEqual(
            await get_bot_global_elo_offset(db), (-180, "database")
        )

    def test_opening_plan_survives_opponent_deviation(self):
        board = chess.Board()
        for uci in ("d2d4", "g8f6", "g1f3", "d7d6"):
            board.push_uci(uci)
        london = search_openings("London System", 1)[0]
        profile = {
            "openings": [{"opening_id": london["id"], "color": "white", "weight": 100}]
        }
        self.assertEqual(
            opening_plan_moves(board, profile), [(chess.Move.from_uci("c1f4"), 100)]
        )

    def test_black_opening_requires_matching_first_move(self):
        board = chess.Board()
        board.push_uci("d2d4")
        sicilian = search_openings("Sicilian Defense", 1)[0]
        profile = {
            "openings": [
                {"opening_id": sicilian["id"], "color": "black", "weight": 100}
            ]
        }
        self.assertEqual(opening_plan_moves(board, profile), [])
        self.assertEqual(
            opening_repertoire_status(board, profile, chess.BLACK), "deviated"
        )

    async def test_low_elo_bot_uses_minimum_limited_engine_strength(self):
        board = chess.Board()
        profile = {
            "target_elo": 800,
            "openings": [],
            "style": {
                "aggression": 50,
                "tacticality": 50,
                "risk": 50,
                "materialism": 50,
                "simplification": 50,
            },
        }
        candidate = chess.Move.from_uci("e2e4")
        engine = AsyncMock()
        engine.analyse.return_value = [
            {
                "pv": [candidate],
                "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
            }
        ]
        engine.quit = AsyncMock()
        with (
            patch("chess_logic.bot_game.os.path.exists", return_value=True),
            patch("chess_logic.bot_game.os.getenv", return_value="/stockfish"),
            patch(
                "chess_logic.bot_game.chess.engine.popen_uci",
                return_value=(None, engine),
            ),
        ):
            move = await choose_bot_move(board, profile)
        self.assertEqual(move, candidate)
        engine.configure.assert_awaited_once_with(
            {"UCI_LimitStrength": True, "UCI_Elo": 1320}
        )

    async def test_extra_weakening_expands_the_candidate_pool(self):
        board = chess.Board()
        profile = {
            "target_elo": 900,
            "extra_weakening": True,
            "openings": [],
            "style": {
                "aggression": 50,
                "tacticality": 50,
                "risk": 50,
                "materialism": 50,
                "simplification": 50,
            },
        }
        candidate = chess.Move.from_uci("e2e4")
        engine = AsyncMock()
        engine.analyse.return_value = [
            {
                "pv": [candidate],
                "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
            }
        ]
        engine.quit = AsyncMock()
        with (
            patch("chess_logic.bot_game.os.path.exists", return_value=True),
            patch("chess_logic.bot_game.os.getenv", return_value="/stockfish"),
            patch(
                "chess_logic.bot_game.chess.engine.popen_uci",
                return_value=(None, engine),
            ),
        ):
            move = await choose_bot_move(board, profile)
        self.assertEqual(move, candidate)
        self.assertEqual(engine.analyse.await_args.kwargs["multipv"], 20)

    async def test_player_and_bot_moves_are_atomic_and_sanitized(self):
        store_dir = tempfile.TemporaryDirectory()
        try:
            bot = BotStore(str(Path(store_dir.name) / "bots.sqlite3")).list()[0]
            manager = BotGameManager()

            async def fake_move(board, profile, rng=None, elo_offset=None):
                self.assertEqual(profile["id"], bot["id"])
                self.assertEqual(elo_offset, -180)
                return chess.Move.from_uci("e7e5")

            with patch("chess_logic.bot_game.choose_bot_move", fake_move):
                started = await manager.start(
                    "session", bot, "white", elo_offset=-180
                )
                self.assertEqual(started["history"], [])
                response = await manager.move("session", "e2e4")
            self.assertEqual(response["history"], ["e2e4", "e7e5"])
            self.assertNotIn("evaluation", response)
            self.assertNotIn("variations", response)
            self.assertFalse(response["llm_commentary_enabled"])
            resigned = manager.resign("session")
            self.assertEqual(resigned["result"], "0-1")
            self.assertIn("Rajko Chess Bot Game", resigned["pgn"])
        finally:
            store_dir.cleanup()

    async def test_llm_commentary_is_generated_only_for_detected_event(self):
        store_dir = tempfile.TemporaryDirectory()
        try:
            bot = BotStore(str(Path(store_dir.name) / "bots.sqlite3")).list()[0]
            manager = BotGameManager()

            async def fake_move(board, profile, rng=None, elo_offset=None):
                return chess.Move.from_uci("e7e5")

            event = {"type": "poważny blunder", "played_move_san": "e4"}
            with (
                patch("chess_logic.bot_game.choose_bot_move", fake_move),
                patch(
                    "chess_logic.bot_game.generate_bot_game_greeting",
                    return_value=LLMResult(text="Zaczynajmy.", usage={}),
                ) as greeting,
                patch(
                    "chess_logic.bot_game.detect_commentary_event", return_value=event
                ) as detect,
                patch(
                    "chess_logic.bot_game.generate_bot_move_commentary",
                    return_value=LLMResult(
                        text="Tego pionka będzie ci brakować.", usage={}
                    ),
                ) as generate,
            ):
                started = await manager.start(
                    "session", bot, "white", llm_commentary=True
                )
                response = await manager.move("session", "e2e4")

            greeting.assert_awaited_once()
            self.assertEqual(started["llm_commentary"], "Zaczynajmy.")
            detect.assert_awaited_once()
            generate.assert_awaited_once()
            self.assertTrue(response["llm_commentary_enabled"])
            self.assertEqual(
                response["llm_commentary"], "Tego pionka będzie ci brakować."
            )
        finally:
            store_dir.cleanup()

    async def test_bot_comments_once_when_game_leaves_favorite_opening(self):
        store_dir = tempfile.TemporaryDirectory()
        try:
            bot = BotStore(str(Path(store_dir.name) / "bots.sqlite3")).list()[1]
            manager = BotGameManager()

            async def fake_move(board, profile, rng=None, elo_offset=None):
                return chess.Move.from_uci("d7d5")

            with (
                patch("chess_logic.bot_game.choose_bot_move", fake_move),
                patch(
                    "chess_logic.bot_game.generate_bot_game_greeting",
                    return_value=LLMResult(text="Czekam na twój ruch.", usage={}),
                ),
                patch(
                    "chess_logic.bot_game.detect_commentary_event", return_value=None
                ),
                patch(
                    "chess_logic.bot_game.generate_bot_move_commentary",
                    return_value=LLMResult(
                        text="Wolałbym sycylijską, ale poradzę sobie także tutaj.",
                        usage={},
                    ),
                ) as generate,
            ):
                await manager.start("session", bot, "white", llm_commentary=True)
                response = await manager.move("session", "d2d4")

            event = generate.await_args.kwargs["event"]
            self.assertEqual(event["type"], "left_favorite_opening")
            self.assertTrue(event["preferred_openings"])
            self.assertIn("sycylijską", response["llm_commentary"].lower())
        finally:
            store_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
