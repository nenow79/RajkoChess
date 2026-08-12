import unittest
import uuid
from types import SimpleNamespace

from auth.cookies import clear_auth_cookies, set_auth_cookies
from auth.dependencies import CurrentAuth
from auth.schemas import RegisterRequest
from auth.security import PASSWORD_HASH, generate_secret, hash_secret
from fastapi import Response
from main import app, get_session_id
from pydantic import ValidationError


class PasswordSecurityTests(unittest.TestCase):
    def test_passwords_use_argon2_and_verify(self):
        password = "bardzo długa fraza szachowa"
        password_digest = PASSWORD_HASH.hash(password)

        self.assertTrue(password_digest.startswith("$argon2"))
        verified, _ = PASSWORD_HASH.verify_and_update(password, password_digest)
        wrong, _ = PASSWORD_HASH.verify_and_update(
            "zupełnie inne hasło", password_digest
        )
        self.assertTrue(verified)
        self.assertFalse(wrong)

    def test_session_secrets_are_random_and_stored_as_sha256(self):
        first = generate_secret()
        second = generate_secret()

        self.assertNotEqual(first, second)
        self.assertEqual(len(hash_secret(first)), 32)
        self.assertNotEqual(hash_secret(first), hash_secret(second))


class AuthSchemaTests(unittest.TestCase):
    def test_registration_rejects_short_and_common_passwords(self):
        with self.assertRaises(ValidationError):
            RegisterRequest(email="test@example.com", password="9znakow!!")
        with self.assertRaises(ValidationError):
            RegisterRequest(email="test@example.com", password="passwordpassword")

        accepted = RegisterRequest(email="test@example.com", password="10znakow!!")
        self.assertEqual(accepted.password, "10znakow!!")

    def test_auth_routes_are_exposed_in_openapi(self):
        paths = app.openapi()["paths"]
        self.assertIn("/api/auth/register", paths)
        self.assertIn("/api/auth/login", paths)
        self.assertIn("/api/auth/me", paths)
        self.assertIn("/api/auth/logout", paths)
        self.assertIn("/api/auth/email-verification/confirm", paths)
        self.assertIn("/api/auth/email-verification/resend", paths)
        logout_parameters = paths["/api/auth/logout"]["post"]["parameters"]
        self.assertTrue(
            any(parameter["name"] == "X-CSRF-Token" for parameter in logout_parameters)
        )

    def test_game_state_uses_authenticated_cookie_not_client_session_header(self):
        paths = app.openapi()["paths"]
        for path, method in (
            ("/api/position", "get"),
            ("/api/move", "post"),
            ("/api/bot-games/current", "get"),
            ("/api/analyze-game", "post"),
        ):
            operation = paths[path][method]
            parameters = operation.get("parameters", [])
            self.assertFalse(
                any(
                    parameter["name"].lower() == "x-session-id"
                    for parameter in parameters
                )
            )
            self.assertIn({"SessionCookie": []}, operation.get("security", []))

    def test_game_state_key_comes_from_database_session_id(self):
        database_session_id = uuid.uuid4()
        current = CurrentAuth(
            session=SimpleNamespace(id=database_session_id),  # type: ignore[arg-type]
            user=SimpleNamespace(),  # type: ignore[arg-type]
        )

        self.assertEqual(get_session_id(current), str(database_session_id))


class AuthCookieTests(unittest.TestCase):
    def test_login_cookie_is_http_only_and_csrf_cookie_is_readable(self):
        response = Response()
        set_auth_cookies(
            response, session_token="session-secret", csrf_token="csrf-secret"
        )
        headers = [
            value.decode("latin-1")
            for name, value in response.raw_headers
            if name == b"set-cookie"
        ]

        self.assertEqual(len(headers), 2)
        session_header = next(
            value for value in headers if value.startswith("rajko_session=")
        )
        csrf_header = next(
            value for value in headers if value.startswith("rajko_csrf=")
        )
        self.assertIn("HttpOnly", session_header)
        self.assertNotIn("HttpOnly", csrf_header)
        self.assertTrue(all("SameSite=lax" in value for value in headers))

    def test_logout_expires_both_cookies(self):
        response = Response()
        clear_auth_cookies(response)
        headers = [
            value.decode("latin-1")
            for name, value in response.raw_headers
            if name == b"set-cookie"
        ]

        self.assertEqual(len(headers), 2)
        self.assertTrue(all("Max-Age=0" in value for value in headers))


if __name__ == "__main__":
    unittest.main()
