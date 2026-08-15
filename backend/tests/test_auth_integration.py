import os
import unittest
from unittest.mock import AsyncMock, patch

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

        logged_out = await self.client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        self.assertEqual(logged_out.status_code, 200, logged_out.text)
        self.assertEqual((await self.client.get("/api/auth/me")).status_code, 401)
