import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

from auth.email import build_password_reset_message
from auth.service import (
    InvalidAuthTokenError,
    create_password_reset_token,
    reset_password_with_token,
)
from db.models import AuthToken, AuthTokenType, Identity, User, UserStatus
from settings import Settings
from sqlalchemy.dialects import postgresql


class PasswordResetEmailTests(unittest.TestCase):
    def test_message_contains_public_one_time_link_and_both_body_formats(self):
        settings = Settings.model_validate(
            {
                "PUBLIC_APP_URL": "https://rajko.pl/chess/",
                "SMTP_USERNAME": "noreply@rajko.pl",
                "SMTP_PASSWORD": "secret",
                "SMTP_FROM_EMAIL": "noreply@rajko.pl",
                "PASSWORD_RESET_MINUTES": 45,
            }
        )

        message = build_password_reset_message(
            recipient="gracz@example.com", token="one-time-secret", settings=settings
        )

        self.assertEqual(message["To"], "gracz@example.com")
        self.assertEqual(message["From"], "Rajko Chess <noreply@rajko.pl>")
        self.assertIn("45 minut", message.get_body(preferencelist=("plain",)).get_content())
        bodies = list(message.iter_parts())
        self.assertEqual(len(bodies), 2)
        self.assertTrue(
            all(
                "https://rajko.pl/chess/reset-password?token=one-time-secret"
                in body.get_content()
                for body in bodies
            )
        )


class PasswordResetTokenTests(unittest.IsolatedAsyncioTestCase):
    async def test_created_token_is_hashed_and_has_short_expiry(self):
        db = AsyncMock()
        db.add = Mock()
        user = User(id=uuid.uuid4(), email="verified@example.com")
        settings = Settings.model_validate({"PASSWORD_RESET_MINUTES": 45})

        with patch("auth.service.get_settings", return_value=settings):
            created = await create_password_reset_token(db, user=user)

        model = db.add.call_args.args[0]
        self.assertIs(model, created.model)
        self.assertEqual(model.type, AuthTokenType.PASSWORD_RESET)
        self.assertEqual(len(model.token_hash), 32)
        self.assertNotEqual(model.token_hash, created.token.encode())
        self.assertEqual(model.expires_at - model.created_at, timedelta(minutes=45))
        db.commit.assert_awaited_once()

    async def test_valid_token_changes_password_consumes_tokens_and_revokes_sessions(self):
        now = datetime.now(timezone.utc)
        user = User(
            id=uuid.uuid4(),
            email="verified@example.com",
            status=UserStatus.ACTIVE,
            email_verified_at=now,
        )
        token = AuthToken(
            id=uuid.uuid4(),
            user_id=user.id,
            type=AuthTokenType.PASSWORD_RESET,
            token_hash=b"x" * 32,
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        token.user = user
        identity = Identity(
            user_id=user.id,
            provider="password",
            provider_subject=user.email,
            password_hash="old-hash",
        )
        db = AsyncMock()
        db.scalar.side_effect = [token, identity]

        with patch(
            "auth.service.hash_password",
            new=AsyncMock(return_value="new-argon-hash"),
        ) as hash_password:
            result = await reset_password_with_token(
                db, token="valid-one-time-secret", new_password="new-password"
            )

        self.assertIs(result, user)
        self.assertEqual(identity.password_hash, "new-argon-hash")
        self.assertIsNotNone(token.consumed_at)
        hash_password.assert_awaited_once_with("new-password")
        self.assertEqual(db.execute.await_count, 2)
        statements = [
            str(call.args[0].compile(dialect=postgresql.dialect()))
            for call in db.execute.await_args_list
        ]
        self.assertIn("UPDATE auth_tokens", statements[0])
        self.assertIn("UPDATE auth_sessions", statements[1])
        self.assertIn("revoked_at IS NULL", statements[1])
        db.commit.assert_awaited_once()

    async def test_expired_token_is_rejected_without_hashing_or_writes(self):
        now = datetime.now(timezone.utc)
        user = User(
            id=uuid.uuid4(),
            email="verified@example.com",
            status=UserStatus.ACTIVE,
            email_verified_at=now,
        )
        token = AuthToken(
            id=uuid.uuid4(),
            user_id=user.id,
            type=AuthTokenType.PASSWORD_RESET,
            token_hash=b"x" * 32,
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        )
        token.user = user
        db = AsyncMock()
        db.scalar.return_value = token

        with (
            patch("auth.service.hash_password", new=AsyncMock()) as hash_password,
            self.assertRaises(InvalidAuthTokenError),
        ):
            await reset_password_with_token(
                db, token="expired-secret", new_password="new-password"
            )

        hash_password.assert_not_awaited()
        db.execute.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_token_lock_targets_only_auth_token_table(self):
        db = AsyncMock()
        db.scalar.return_value = None

        with self.assertRaises(InvalidAuthTokenError):
            await reset_password_with_token(
                db, token="invalid-secret", new_password="new-password"
            )

        statement = db.scalar.await_args.args[0]
        sql = str(statement.compile(dialect=postgresql.dialect()))
        self.assertIn("FOR UPDATE OF auth_tokens", sql)


if __name__ == "__main__":
    unittest.main()
