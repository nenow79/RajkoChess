import unittest
from unittest.mock import AsyncMock, Mock, patch

from chess_logic.lichess import _parse_games, get_opening_explorer_data, get_recent_games


LICHESS_PGN = '''[Event "Rated Rapid game"]
[Site "https://lichess.org/AbCd1234"]
[Date "2026.09.08"]
[UTCDate "2026.09.08"]
[UTCTime "18:42:10"]
[White "Example_Player"]
[Black "Opponent"]
[Result "1-0"]
[WhiteElo "1612"]
[BlackElo "1598"]
[TimeControl "600+0"]

1. e4 e5 2. Nf3 Nc6 1-0
'''


class LichessExplorerTests(unittest.IsolatedAsyncioTestCase):
    def test_user_export_is_parsed_into_importable_game(self):
        result = _parse_games(LICHESS_PGN, "example_player", 12)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "AbCd1234")
        self.assertEqual(result[0]["source"], "lichess")
        self.assertEqual(result[0]["color"], "white")
        self.assertEqual(result[0]["result"], "win")
        self.assertEqual(result[0]["opponent"], "Opponent")
        self.assertEqual(result[0]["rating"], 1612)
        self.assertEqual(result[0]["time_class"], "rapid")
        self.assertEqual(result[0]["move_count"], 2)
        self.assertEqual(result[0]["played_at"], "2026-09-08T18:42:10+00:00")

    async def test_recent_games_uses_bounded_public_export(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = LICHESS_PGN
        client = AsyncMock()
        client.get.return_value = response

        with patch("chess_logic.lichess.httpx.AsyncClient") as client_class:
            client_class.return_value.__aenter__.return_value = client
            result = await get_recent_games("Example_Player", 200)

        self.assertEqual(len(result), 1)
        request = client.get.await_args
        self.assertEqual(request.args[0], "https://lichess.org/api/games/user/Example_Player")
        self.assertEqual(request.kwargs["params"]["max"], 30)
        self.assertEqual(request.kwargs["params"]["finished"], "true")

    async def test_local_opening_fallback_does_not_make_more_http_requests(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "white": 0,
            "draws": 0,
            "black": 0,
            "opening": None,
            "moves": [],
        }
        client = AsyncMock()
        client.get.return_value = response

        with patch("chess_logic.lichess.httpx.AsyncClient") as client_class:
            client_class.return_value.__aenter__.return_value = client
            result = await get_opening_explorer_data(
                "test-fen",
                fallback_opening={"name": "Ruy Lopez", "eco": "C60"},
            )

        client.get.assert_awaited_once()
        self.assertEqual(result["opening_name"], "Ruy Lopez")
        self.assertEqual(result["opening_eco"], "C60")
        self.assertTrue(result["opening_is_fallback"])


if __name__ == "__main__":
    unittest.main()
