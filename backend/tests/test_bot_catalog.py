import unittest
import uuid

from chess_logic.bot_catalog import can_manage_bot, parse_visibility
from db.models import Bot, BotVisibility, SystemRole, User
from main import app


class BotPolicyTests(unittest.TestCase):
    def setUp(self):
        self.owner = User(id=uuid.uuid4(), email="owner@example.com")
        self.other_user = User(id=uuid.uuid4(), email="other@example.com")
        self.admin = User(
            id=uuid.uuid4(), email="admin@example.com", system_role=SystemRole.ADMIN
        )

    def test_private_bot_can_only_be_managed_by_its_owner(self):
        bot = Bot(
            owner_id=self.owner.id,
            visibility=BotVisibility.PRIVATE,
            name="Prywatny",
            description="Bot właściciela",
            avatar="🤖",
            target_elo=1400,
            extra_weakening=False,
            style={},
            openings=[],
            phrases={},
        )

        self.assertTrue(can_manage_bot(bot, self.owner))
        self.assertFalse(can_manage_bot(bot, self.other_user))
        self.assertFalse(can_manage_bot(bot, self.admin))

    def test_public_bot_can_only_be_managed_by_admin(self):
        bot = Bot(
            owner_id=None,
            visibility=BotVisibility.PUBLIC,
            name="Publiczny",
            description="Bot systemowy",
            avatar="♟️",
            target_elo=1600,
            extra_weakening=False,
            style={},
            openings=[],
            phrases={},
        )

        self.assertFalse(can_manage_bot(bot, self.owner))
        self.assertTrue(can_manage_bot(bot, self.admin))

    def test_visibility_is_explicit_and_validated(self):
        self.assertEqual(
            parse_visibility(None, default=BotVisibility.PRIVATE), BotVisibility.PRIVATE
        )
        self.assertEqual(
            parse_visibility("public", default=BotVisibility.PRIVATE),
            BotVisibility.PUBLIC,
        )
        with self.assertRaises(ValueError):
            parse_visibility("shared", default=BotVisibility.PRIVATE)

    def test_bot_writes_require_cookie_and_csrf_header(self):
        paths = app.openapi()["paths"]
        for path, method in (
            ("/api/bots", "post"),
            ("/api/bots/{bot_id}", "put"),
            ("/api/bots/{bot_id}", "delete"),
        ):
            operation = paths[path][method]
            parameters = operation.get("parameters", [])
            self.assertIn({"SessionCookie": []}, operation.get("security", []))
            self.assertTrue(
                any(parameter["name"] == "X-CSRF-Token" for parameter in parameters)
            )


if __name__ == "__main__":
    unittest.main()
