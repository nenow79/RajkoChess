import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from auth.platform_accounts import (
    normalize_platform_username,
    upsert_platform_account,
)


class PlatformAccountTests(unittest.IsolatedAsyncioTestCase):
    def test_chesscom_username_is_validated_and_normalized(self):
        self.assertEqual(
            normalize_platform_username("chesscom", " Beta_Player "),
            ("Beta_Player", "beta_player"),
        )
        with self.assertRaisesRegex(ValueError, "Login Chess.com"):
            normalize_platform_username("chesscom", "niedozwolony login!")
        with self.assertRaisesRegex(ValueError, "Nieobsługiwana"):
            normalize_platform_username("unknown", "player")

    async def test_new_platform_username_is_owned_by_current_user(self):
        owner_id = uuid.uuid4()
        db = SimpleNamespace(
            scalar=AsyncMock(return_value=None),
            add=Mock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )

        model = await upsert_platform_account(
            db,  # type: ignore[arg-type]
            user=SimpleNamespace(id=owner_id),  # type: ignore[arg-type]
            provider="chesscom",
            username="Beta_Player",
        )

        self.assertEqual(model.user_id, owner_id)
        self.assertEqual(model.normalized_username, "beta_player")
        db.add.assert_called_once_with(model)
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(model)


if __name__ == "__main__":
    unittest.main()
