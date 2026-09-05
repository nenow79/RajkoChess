import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import AsyncMock, patch

from auth.google_oauth import (
    GoogleOAuthError,
    build_authorization_url,
    exchange_code_for_claims,
)
from auth.router import _set_google_oauth_cookies
from fastapi import Response
from settings import Settings


def google_settings() -> Settings:
    return Settings.model_validate(
        {
            "GOOGLE_OAUTH_CLIENT_ID": "client-id.apps.googleusercontent.com",
            "GOOGLE_OAUTH_CLIENT_SECRET": "client-secret",
            "GOOGLE_OAUTH_REDIRECT_URI": "https://rajko.pl/chess/api/auth/google/callback",
            "RATE_LIMIT_KEY_SECRET": "x" * 32,
        }
    )


class FakeTokenResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"id_token": "signed-token"}


class FakeHttpClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, *_args, **_kwargs) -> FakeTokenResponse:
        return FakeTokenResponse()


class GoogleOAuthTests(unittest.IsolatedAsyncioTestCase):
    def test_authorization_url_uses_code_flow_state_and_nonce(self):
        with patch("auth.google_oauth.get_settings", return_value=google_settings()):
            url = build_authorization_url(
                state="state-secret",
                nonce="nonce-secret",
                code_verifier="v" * 43,
            )

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "accounts.google.com")
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["scope"], ["openid email profile"])
        self.assertEqual(query["state"], ["state-secret"])
        self.assertEqual(query["nonce"], ["nonce-secret"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertIn("code_challenge", query)
        self.assertEqual(
            query["redirect_uri"],
            ["https://rajko.pl/chess/api/auth/google/callback"],
        )

    async def test_verified_claims_require_matching_nonce_and_verified_email(self):
        verified_claims = {
            "sub": "google-subject",
            "email": "Player@Example.com",
            "email_verified": True,
            "name": "  Gracz  ",
            "nonce": "expected-nonce",
        }
        with (
            patch("auth.google_oauth.get_settings", return_value=google_settings()),
            patch("auth.google_oauth.httpx.AsyncClient", return_value=FakeHttpClient()),
            patch(
                "auth.google_oauth._verify_id_token",
                new=AsyncMock(return_value=verified_claims),
            ),
            patch(
                "auth.google_oauth.run_in_threadpool",
                new=AsyncMock(return_value=verified_claims),
            ),
        ):
            claims = await exchange_code_for_claims(
                code="authorization-code",
                expected_nonce="expected-nonce",
                code_verifier="v" * 43,
            )
            self.assertEqual(claims.subject, "google-subject")
            self.assertEqual(claims.email, "player@example.com")
            self.assertEqual(claims.display_name, "Gracz")

            verified_claims["nonce"] = "wrong-nonce"
            with self.assertRaises(GoogleOAuthError):
                await exchange_code_for_claims(
                    code="authorization-code",
                    expected_nonce="expected-nonce",
                    code_verifier="v" * 43,
                )

    def test_oauth_transaction_cookies_are_short_lived_and_http_only(self):
        response = Response()
        with patch("auth.router.get_settings", return_value=google_settings()):
            _set_google_oauth_cookies(
                response,
                state_value="state-secret",
                nonce="nonce-secret",
                code_verifier="v" * 43,
                intent="login",
            )
        headers = [
            value.decode("latin-1")
            for name, value in response.raw_headers
            if name == b"set-cookie"
        ]
        self.assertEqual(len(headers), 4)
        self.assertTrue(all("HttpOnly" in value for value in headers))
        self.assertTrue(all("Max-Age=600" in value for value in headers))
        self.assertTrue(all("SameSite=lax" in value for value in headers))
        self.assertTrue(all("Path=/" in value for value in headers))


if __name__ == "__main__":
    unittest.main()
