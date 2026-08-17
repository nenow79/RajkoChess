import os
import unittest
import uuid
from unittest.mock import AsyncMock, patch

from db.models import ChatMessage
from db.session import get_db_session, get_engine
from httpx import ASGITransport, AsyncClient
from main import app
from sqlalchemy.ext.asyncio import AsyncSession


@unittest.skipUnless(
    os.getenv("RUN_DATABASE_INTEGRATION_TESTS") == "1",
    "wymaga testowego PostgreSQL i jawnego RUN_DATABASE_INTEGRATION_TESTS=1",
)
class AuthenticationApiIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.connection = await get_engine().connect()
        self.transaction = await self.connection.begin()
        self.db = AsyncSession(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def override_db_session():
            try:
                yield self.db
            except Exception:
                await self.db.rollback()
                raise

        app.dependency_overrides[get_db_session] = override_db_session
        self.tokens: list[str] = []

        async def capture_verification_email(*, recipient: str, token: str) -> None:
            self.assertEqual(recipient, "beta@example.com")
            self.tokens.append(token)

        self.rate_patch = patch(
            "auth.router.enforce_rate_limit", new=AsyncMock()
        )
        self.clear_rate_patch = patch(
            "auth.router.clear_rate_limit", new=AsyncMock()
        )
        self.email_patch = patch(
            "auth.router.send_verification_email",
            new=capture_verification_email,
        )
        self.rate_patch.start()
        self.clear_rate_patch.start()
        self.email_patch.start()
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        self.email_patch.stop()
        self.clear_rate_patch.stop()
        self.rate_patch.stop()
        app.dependency_overrides.clear()
        await self.db.close()
        await self.transaction.rollback()
        await self.connection.close()

    async def test_register_verify_login_me_and_logout(self):
        credentials = {
            "email": "beta@example.com",
            "password": "bezpieczne-haslo-beta",
            "display_name": "Beta Tester",
        }
        registered = await self.client.post("/api/auth/register", json=credentials)
        self.assertEqual(registered.status_code, 201, registered.text)
        self.assertEqual(len(self.tokens), 1)

        unverified_login = await self.client.post(
            "/api/auth/login",
            json={"email": credentials["email"], "password": credentials["password"]},
        )
        self.assertEqual(unverified_login.status_code, 403)

        verified = await self.client.post(
            "/api/auth/email-verification/confirm",
            json={"token": self.tokens[0]},
        )
        self.assertEqual(verified.status_code, 200, verified.text)

        logged_in = await self.client.post(
            "/api/auth/login",
            json={"email": credentials["email"], "password": credentials["password"]},
        )
        self.assertEqual(logged_in.status_code, 200, logged_in.text)
        csrf_token = logged_in.json()["csrf_token"]

        current = await self.client.get("/api/auth/me")
        self.assertEqual(current.status_code, 200, current.text)
        self.assertEqual(current.json()["email"], credentials["email"])

        saved_platform = await self.client.put(
            "/api/auth/platform-accounts/chesscom",
            json={"username": "Beta_Player"},
            headers={"X-CSRF-Token": csrf_token},
        )
        self.assertEqual(saved_platform.status_code, 200, saved_platform.text)
        self.assertEqual(saved_platform.json()["username"], "Beta_Player")
        platform_accounts = await self.client.get("/api/auth/platform-accounts")
        self.assertEqual(
            platform_accounts.json()["accounts"][0]["provider"], "chesscom"
        )

        pgn = (
            '[Event "Beta"]\n[Site "Local"]\n[Date "2026.08.15"]\n'
            '[Round "1"]\n[White "Beta"]\n[Black "Tester"]\n'
            '[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 1-0'
        )
        import_payload = {
            "pgn": pgn,
            "metadata": {
                "id": "integration-game-1",
                "source": "chesscom",
                "opponent": "Tester",
                "result": "1-0",
                "played_at": "2026-08-15T12:00:00Z",
            },
        }
        first_import = await self.client.post(
            "/api/import-game",
            json=import_payload,
            headers={"X-CSRF-Token": csrf_token},
        )
        self.assertEqual(first_import.status_code, 200, first_import.text)
        game_id = first_import.json()["game_id"]

        second_import = await self.client.post(
            "/api/import-game",
            json=import_payload,
            headers={"X-CSRF-Token": csrf_token},
        )
        self.assertEqual(second_import.status_code, 200, second_import.text)
        self.assertEqual(second_import.json()["game_id"], game_id)

        history = await self.client.get("/api/games")
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(len(history.json()["games"]), 1)
        self.assertEqual(history.json()["games"][0]["opponent"], "Tester")
        self.assertFalse(history.json()["games"][0]["has_analysis"])

        self.db.add_all(
            [
                ChatMessage(
                    owner_id=uuid.UUID(current.json()["id"]),
                    game_id=uuid.UUID(game_id),
                    role="user",
                    kind="position",
                    content="Jaki jest plan w tej pozycji?",
                    fen=first_import.json()["fen"],
                ),
                ChatMessage(
                    owner_id=uuid.UUID(current.json()["id"]),
                    game_id=uuid.UUID(game_id),
                    role="assistant",
                    kind="position",
                    content="Rozwijaj figury i walcz o centrum.",
                    fen=first_import.json()["fen"],
                ),
            ]
        )
        await self.db.commit()

        chat_history = await self.client.get(f"/api/games/{game_id}/chat")
        self.assertEqual(chat_history.status_code, 200, chat_history.text)
        self.assertEqual(len(chat_history.json()["messages"]), 2)
        self.assertEqual(chat_history.json()["messages"][1]["role"], "assistant")

        history_with_chat = await self.client.get("/api/games")
        self.assertTrue(history_with_chat.json()["games"][0]["has_analysis"])

        cleared_chat = await self.client.delete(
            f"/api/games/{game_id}/chat",
            headers={"X-CSRF-Token": csrf_token},
        )
        self.assertEqual(cleared_chat.status_code, 200, cleared_chat.text)
        self.assertFalse(cleared_chat.json()["has_analysis"])
        self.assertEqual(
            (await self.client.get(f"/api/games/{game_id}/chat")).json()["messages"],
            [],
        )

        opened = await self.client.post(
            f"/api/games/{game_id}/open",
            headers={"X-CSRF-Token": csrf_token},
        )
        self.assertEqual(opened.status_code, 200, opened.text)
        self.assertEqual(opened.json()["game_id"], game_id)
        self.assertEqual(opened.json()["metadata"]["opponent"], "Tester")

        logged_out = await self.client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        self.assertEqual(logged_out.status_code, 200, logged_out.text)
        self.assertEqual((await self.client.get("/api/auth/me")).status_code, 401)
