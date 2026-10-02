import unittest
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from pydantic import ValidationError

from chess_logic.game import ChessGame
from chess_logic.llm_agent import LLMResult
from main import GameReviewRequest, analyze_imported_game, last_ai_analyses


class GameReviewStyleTests(unittest.IsolatedAsyncioTestCase):
    def test_request_defaults_and_rejects_unknown_style(self):
        self.assertEqual(
            GameReviewRequest(message="Analizuj partię").analysis_style, "grounded"
        )
        with self.assertRaises(ValidationError):
            GameReviewRequest(message="Analizuj partię", analysis_style="unknown")

    async def test_styles_keep_perspective_and_persist_report_metadata(self):
        for style in ("grounded", "freestyle"):
            for focus in ("white", "black", "both"):
                with self.subTest(style=style, focus=focus):
                    game_id = uuid.uuid4()
                    session_id = str(uuid.uuid4())
                    game = ChessGame()
                    game.load_pgn(
                        "1. e4 e5 *", {"color": "black"}, game_id=str(game_id)
                    )
                    usage = {}

                    @asynccontextmanager
                    async def limited(*args, **kwargs):
                        yield usage

                    engine = AsyncMock(return_value={"critical_moments": []})
                    coach = AsyncMock(return_value=LLMResult(text="Raport", usage={}))
                    save = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
                    chat = AsyncMock()
                    self.addCleanup(last_ai_analyses.pop, session_id, None)
                    with (
                        patch("main.limited_operation", limited),
                        patch("main.analyze_game", engine),
                        patch("main.generate_game_analysis", coach),
                        patch("main.record_completed_analysis", save),
                        patch("main.add_chat_messages", chat),
                    ):
                        result = await analyze_imported_game(
                            request=GameReviewRequest(
                                message="Przeanalizuj całą partię.",
                                focus_color=focus,
                                analysis_style=style,
                            ),
                            game=game,
                            session_id=session_id,
                            current=SimpleNamespace(user=SimpleNamespace(id=uuid.uuid4())),
                            db=Mock(),
                        )
                    self.assertEqual(engine.await_args.kwargs["focus_color"], None if focus == "both" else focus)
                    self.assertEqual(coach.await_args.kwargs["analysis_style"], style)
                    if focus == "both":
                        self.assertEqual(coach.await_args.kwargs["engine_analysis"]["focus_scope"], "both")
                    self.assertEqual(save.await_args.kwargs["engine_result"]["analysis_style"], style)
                    self.assertEqual(save.await_args.kwargs["coach_response"], "Raport")
                    self.assertEqual(chat.await_args.kwargs["messages"][1], ("assistant", "game_review", "Raport"))
                    self.assertEqual(result["engine_analysis"]["analysis_style"], style)
                    self.assertEqual(usage["analysis_style"], style)
