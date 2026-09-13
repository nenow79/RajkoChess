import unittest

import chess

from chess_logic.engine import _played_move_facts, _variation_evidence
from chess_logic.llm_agent import _render_grounded_game_review


class EngineGroundingTests(unittest.TestCase):
    # Position from the reported 17...Na4 hallucination. White is to move.
    FEN_AFTER_NA4 = "2r2rk1/1p3ppp/pq1bpn2/3p4/n2N4/2B1P1P1/PP2PPBP/2RQ1RK1 w - - 0 18"

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


if __name__ == "__main__":
    unittest.main()
