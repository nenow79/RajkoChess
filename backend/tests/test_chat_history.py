import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from chess_logic.chat_history import add_chat_messages


class ChatHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_exchange_is_linked_to_owner_game_and_position(self):
        owner_id = uuid.uuid4()
        game_id = uuid.uuid4()
        db = SimpleNamespace(add_all=Mock(), flush=AsyncMock())

        models = await add_chat_messages(
            db,  # type: ignore[arg-type]
            user=SimpleNamespace(id=owner_id),  # type: ignore[arg-type]
            game_id=game_id,
            messages=(
                ("user", "position", "Jaki ruch?"),
                ("assistant", "position", "Najlepsze jest e4."),
            ),
            fen="8/8/8/8/8/8/8/K6k w - - 0 1",
            position_ply=17,
        )

        self.assertEqual([model.role for model in models], ["user", "assistant"])
        self.assertEqual([model.message_order for model in models], [0, 1])
        self.assertTrue(all(model.owner_id == owner_id for model in models))
        self.assertTrue(all(model.game_id == game_id for model in models))
        self.assertTrue(all(model.fen is not None for model in models))
        self.assertTrue(all(model.position_ply == 17 for model in models))
        db.add_all.assert_called_once_with(models)
        db.flush.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
