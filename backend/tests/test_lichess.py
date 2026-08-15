import unittest
from unittest.mock import AsyncMock, Mock, patch

from chess_logic.lichess import get_opening_explorer_data


class LichessExplorerTests(unittest.IsolatedAsyncioTestCase):
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
