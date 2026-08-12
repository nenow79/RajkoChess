import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

from auth.email import build_verification_message
from auth.service import (
    EmailNotVerifiedError,
    InvalidAuthTokenError,
    authenticate_user,
    create_email_verification_token,
    verify_email_token,
)
from db.models import AuthToken, AuthTokenType, Identity, User, UserStatus
from settings import Settings
from sqlalchemy.dialects import postgresql


class VerificationEmailTests(unittest.TestCase):
    def test_message_contains_public_one_time_link_and_both_body_formats(self):
        settings = Settings.model_validate(
            {
                "PUBLIC_APP_URL": "https://chess.rajko.pl/",
                "SMTP_USERNAME": "noreply@rajko.pl",
                "SMTP_PASSWORD": "secret",
                "SMTP_FROM_EMAIL": "noreply@rajko.pl",
            }
        )

        message = build_verification_message(
            recipient="gracz@example.com", token="one-time-secret", settings=settings
        )

        self.assertEqual(message["To"], "gracz@example.com")
        self.assertEqual(message["From"], "Rajko Chess <noreply@rajko.pl>")
        bodies = list(message.iter_parts())
        self.assertEqual(len(bodies), 2)
        self.assertTrue(
            all(
                "https://chess.rajko.pl/verify-email?token=one-time-secret"
                in body.get_content()
                for body in bodies
            )
        )

    def test_smtp_configuration_reports_names_but_never_secret_values(self):
        settings = Settings.model_validate(
            {
                "SMTP_USERNAME": "",
                "SMTP_PASSWORD": "do-not-print",
                "SMTP_FROM_EMAIL": "",
            }
        )
        with self.assertRaisesRegex(
            RuntimeError, "SMTP_USERNAME, SMTP_FROM_EMAIL"
        ) as error:
            settings.require_smtp()
        self.assertNotIn("do-not-print", str(error.exception))


class VerificationTokenTests(unittest.IsolatedAsyncioTestCase):
    async def test_created_token_is_hashed_and_expires_after_configured_time(self):
        db = AsyncMock()
        db.add = Mock()
        user = User(id=uuid.uuid4(), email="new@example.com", status=UserStatus.ACTIVE)
        settings = Settings.model_validate({"EMAIL_VERIFICATION_HOURS": 24})

        with patch("auth.service.get_settings", return_value=settings):
            created = await create_email_verification_token(db, user=user)

        model = db.add.call_args.args[0]
        self.assertIs(model, created.model)
        self.assertEqual(model.type, AuthTokenType.EMAIL_VERIFICATION)
        self.assertEqual(len(model.token_hash), 32)
        self.assertNotEqual(model.token_hash, created.token.encode())
        self.assertEqual(model.expires_at - model.created_at, timedelta(hours=24))
        db.commit.assert_awaited_once()

    async def test_valid_token_verifies_user_and_is_consumed(self):
        now = datetime.now(timezone.utc)
        user = User(id=uuid.uuid4(), email="new@example.com")
        model = AuthToken(
            id=uuid.uuid4(),
            user_id=user.id,
            type=AuthTokenType.EMAIL_VERIFICATION,
            token_hash=b"x" * 32,
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        model.user = user
        db = AsyncMock()
        db.scalar.return_value = model

        verified_user = await verify_email_token(db, token="valid-secret-token")

        self.assertIs(verified_user, user)
        self.assertIsNotNone(user.email_verified_at)
        self.assertIsNotNone(model.consumed_at)
        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()

    async def test_expired_token_is_rejected_without_database_write(self):
        now = datetime.now(timezone.utc)
        user = User(id=uuid.uuid4(), email="new@example.com")
        model = AuthToken(
            id=uuid.uuid4(),
            user_id=user.id,
            type=AuthTokenType.EMAIL_VERIFICATION,
            token_hash=b"x" * 32,
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        )
        model.user = user
        db = AsyncMock()
        db.scalar.return_value = model

        with self.assertRaises(InvalidAuthTokenError):
            await verify_email_token(db, token="expired-secret-token")
        db.execute.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_token_lock_targets_only_auth_token_table(self):
        db = AsyncMock()
        db.scalar.return_value = None

        with self.assertRaises(InvalidAuthTokenError):
            await verify_email_token(db, token="invalid-secret-token")

        statement = db.scalar.await_args.args[0]
        sql = str(statement.compile(dialect=postgresql.dialect()))
        self.assertIn("FOR UPDATE OF auth_tokens", sql)

    async def test_correct_password_cannot_create_session_before_verification(self):
        user = User(id=uuid.uuid4(), email="new@example.com", status=UserStatus.ACTIVE)
        identity = Identity(
            user_id=user.id,
            provider="password",
            provider_subject=user.email,
            password_hash="argon-hash",
        )
        identity.user = user
        db = AsyncMock()
        db.scalar.return_value = identity

        with (
            patch(
                "auth.service.verify_password",
                new=AsyncMock(return_value=(True, None)),
            ),
            self.assertRaises(EmailNotVerifiedError),
        ):
            await authenticate_user(db, email=user.email, password="correct-password")


if __name__ == "__main__":
    unittest.main()
