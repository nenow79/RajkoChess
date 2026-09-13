import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import chess
import chess.engine

from chess_logic.engine import (
    _played_move_facts,
    _variation_evidence,
    analyze_position,
    find_legal_move_in_text,
)
from chess_logic.llm_agent import (
    _render_grounded_game_review,
    _render_grounded_position_analysis,
)


class EngineGroundingTests(unittest.TestCase):
    # Position from the reported 17...Na4 hallucination. White is to move.
    FEN_AFTER_NA4 = "2r2rk1/1p3ppp/pq1bpn2/3p4/n2N4/2B1P1P1/PP2PPBP/2RQ1RK1 w - - 0 18"

    def test_question_move_is_resolved_only_when_unambiguous_and_legal(self):
        initial = chess.Board().fen()
        self.assertEqual(
            find_legal_move_in_text(initial, "Dlaczego e4 jest dobrym ruchem?"),
            "e2e4",
        )
        self.assertEqual(
            find_legal_move_in_text(initial, "Czy Sf3 rozwija figurę?"),
            "g1f3",
        )
        self.assertIsNone(
            find_legal_move_in_text(initial, "Porównaj e4 oraz d4.")
        )
        self.assertIsNone(
            find_legal_move_in_text(initial, "Czy e5 jest teraz legalne?")
        )

    def test_castling_is_understood_from_natural_language_without_guessing(self):
        both_castles = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
        self.assertEqual(
            find_legal_move_in_text(both_castles, "Czy krótka roszada jest dobra?"),
            "e1g1",
        )
        self.assertEqual(
            find_legal_move_in_text(both_castles, "A co z długą roszadą?"),
            "e1c1",
        )
        self.assertIsNone(
            find_legal_move_in_text(both_castles, "Czy roszada jest dobra?")
        )
        only_short = "4k3/8/8/8/8/8/8/4K2R w K - 0 1"
        self.assertEqual(
            find_legal_move_in_text(only_short, "Czy roszada jest dobra?"),
            "e1g1",
        )

    def test_punishment_line_is_legal_and_tracks_material(self):
        board = chess.Board(self.FEN_AFTER_NA4)
        moves = []
        for san in ("Qxa4", "Rxc3", "bxc3"):
            move = board.parse_san(san)
            moves.append(move)
            board.push(move)

        evidence = _variation_evidence(
            chess.Board(self.FEN_AFTER_NA4), moves, perspective="black"
        )

        self.assertEqual(
            [item["move_label"] for item in evidence["line"]],
            ["18. Qxa4", "18... Rxc3", "19. bxc3"],
        )
        self.assertEqual(evidence["material_change_for_mover"], -5)
        self.assertEqual(
            [item["captured"]["piece"] for item in evidence["captures"]],
            ["knight", "bishop", "rook"],
        )

    def test_na4_attacks_bishop_and_pawn_but_not_queen(self):
        after_board = chess.Board(self.FEN_AFTER_NA4)
        before_board = after_board.copy()
        move = chess.Move.from_uci("c5a4")
        before_board.remove_piece_at(chess.A4)
        before_board.set_piece_at(chess.C5, chess.Piece(chess.KNIGHT, chess.BLACK))
        before_board.turn = chess.BLACK
        before_board.fullmove_number = 17

        facts = _played_move_facts(before_board, move, after_board)
        attacked = {
            (item["piece"], item["square"])
            for item in facts["directly_attacks_after_move"]
        }

        self.assertEqual(attacked, {("pawn", "b2"), ("bishop", "c3")})
        self.assertNotIn(("queen", "d1"), attacked)

    def test_grounded_report_does_not_invent_queen_attack(self):
        after_board = chess.Board(self.FEN_AFTER_NA4)
        before_board = after_board.copy()
        move = chess.Move.from_uci("c5a4")
        before_board.remove_piece_at(chess.A4)
        before_board.set_piece_at(chess.C5, chess.Piece(chess.KNIGHT, chess.BLACK))
        before_board.turn = chess.BLACK

        line_board = after_board.copy()
        moves = []
        for san in ("Qxa4", "Rxc3", "bxc3"):
            reply = line_board.parse_san(san)
            moves.append(reply)
            line_board.push(reply)

        review = _render_grounded_game_review(
            {
                "overview": "Analiza oparta na danych silnika.",
                "moments": [],
                "root_causes": [],
                "training_recommendations": ["Ćwicz kalkulację."],
            },
            critical_moments=[
                {
                    "ply": 34,
                    "move_label": "17... Na4",
                    "evaluation_before": -0.1,
                    "evaluation_after": 5.3,
                    "loss": 5.4,
                    "played_move_facts": _played_move_facts(
                        before_board, move, after_board
                    ),
                    "punishment": _variation_evidence(
                        after_board, moves, perspective="black"
                    ),
                    "better_alternative": {"line": []},
                }
            ],
            focus_color="black",
        )

        self.assertIn("biały pion b2", review)
        self.assertIn("biały goniec c3", review)
        self.assertIn("18. Qxa4 18... Rxc3 19. bxc3", review)
        self.assertNotIn("hetman d1", review)

    def test_position_report_uses_only_engine_move_and_attack_facts(self):
        board = chess.Board()
        move = board.parse_san("Nf3")
        after = board.copy()
        after.push(move)
        reply = after.parse_san("d5")
        report = _render_grounded_position_analysis(
            {
                "summary": "Rozwój figur jest najważniejszy.",
                "line_explanations": [],
                "requested_move_explanation": "Ruch zachowuje równowagę.",
                "plans": ["Walcz o centrum."],
                "practical_tip": "Sprawdzaj odpowiedź przeciwnika.",
            },
            stockfish_data={
                "side_to_move": "white",
                "variations": [
                    {
                        "evaluation": 0.2,
                        "evidence": _variation_evidence(board, [move]),
                    }
                ],
                "requested_move": {
                    "move_label": "1. Nf3",
                    "san": "Nf3",
                    "uci": "g1f3",
                    "evaluation_before": 0.2,
                    "evaluation_after": 0.1,
                    "loss": 0.1,
                    "root_depth": 14,
                    "response_depth": 13,
                    "move_facts": _played_move_facts(board, move, after),
                    "continuation": _variation_evidence(after, [reply]),
                },
            },
            lichess_data={
                "top_moves": [
                    {"san": "Nf3", "uci": "g1f3", "play_rate_pct": 42.5}
                ]
            },
        )

        self.assertIn("**Krótka odpowiedź:** Tak", report)
        self.assertIn("42.5% partii", report)
        self.assertIn("1. Nf3", report)
        self.assertIn("1... d5", report)
        self.assertIn("Głębokość analizy: pozycja 14, odpowiedź 13", report)
        self.assertIn("**Na ruchu:** białe", report)


class PositionEngineGroundingTests(unittest.IsolatedAsyncioTestCase):
    async def test_requested_move_gets_its_own_engine_evaluation(self):
        board = chess.Board()
        best = board.parse_san("e4")
        candidate = board.parse_san("Nf3")
        best_reply_board = board.copy()
        best_reply_board.push(best)
        best_reply = best_reply_board.parse_san("e5")
        candidate_board = board.copy()
        candidate_board.push(candidate)
        candidate_reply = candidate_board.parse_san("d5")

        engine = SimpleNamespace(
            analyse=AsyncMock(
                side_effect=[
                    [
                        {
                            "score": chess.engine.PovScore(
                                chess.engine.Cp(20), chess.WHITE
                            ),
                            "pv": [best, best_reply],
                            "depth": 14,
                        }
                    ],
                    {
                        "score": chess.engine.PovScore(
                            chess.engine.Cp(5), chess.WHITE
                        ),
                        "pv": [candidate, candidate_reply],
                        "depth": 13,
                    },
                ]
            ),
            quit=AsyncMock(),
        )
        with (
            patch("chess_logic.engine.os.getenv", return_value="/stockfish"),
            patch("chess_logic.engine.os.path.exists", return_value=True),
            patch(
                "chess_logic.engine.chess.engine.popen_uci",
                new=AsyncMock(return_value=(None, engine)),
            ),
        ):
            result = await analyze_position(
                board.fen(), requested_move_uci=candidate.uci()
            )

        requested = result["requested_move"]
        self.assertEqual(result["side_to_move"], "white")
        self.assertEqual(requested["move_label"], "1. Nf3")
        self.assertEqual(requested["loss"], 0.15)
        self.assertEqual(
            requested["continuation"]["line"][0]["move_label"], "1... d5"
        )
        engine.quit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
