import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from rate_limit import (
    RateLimitStoreUnavailable,
    consume_rate_limit,
    enforce_rate_limit,
    private_key,
)
from settings import Settings


class RateLimitPrivacyTests(unittest.TestCase):
    def test_identifiers_are_hmac_hashed_and_case_insensitive(self):
        settings = Settings.model_validate({"RATE_LIMIT_KEY_SECRET": "t" * 32})
        with patch("rate_limit.get_settings", return_value=settings):
            first = private_key("Player@Example.com")
            second = private_key("player@example.com")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        self.assertNotIn("player", first)


class RedisRateLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_limit_returns_retry_after_and_429(self):
        redis = AsyncMock()
        redis.eval.side_effect = [[1, 60], [3, 42]]
        settings = Settings.model_validate({"RATE_LIMIT_KEY_SECRET": "t" * 32})
        with (
            patch("rate_limit.get_redis", return_value=redis),
            patch("rate_limit.get_settings", return_value=settings),
        ):
            count, ttl = await consume_rate_limit(
                bucket="login", identity="127.0.0.1", limit=2, window_seconds=60
            )
            self.assertEqual((count, ttl), (1, 60))
            with self.assertRaises(HTTPException) as error:
                await consume_rate_limit(
                    bucket="login",
                    identity="127.0.0.1",
                    limit=2,
                    window_seconds=60,
                )
        self.assertEqual(error.exception.status_code, 429)
        self.assertEqual(error.exception.headers, {"Retry-After": "42"})

    async def test_fail_closed_and_fail_open_are_explicit(self):
        with patch(
            "rate_limit.consume_rate_limit",
            new=AsyncMock(side_effect=RateLimitStoreUnavailable),
        ), patch("rate_limit.logger.exception"):
            with self.assertRaises(HTTPException) as error:
                await enforce_rate_limit(
                    bucket="email", identity="x", limit=1, window_seconds=60
                )
            self.assertEqual(error.exception.status_code, 503)
            await enforce_rate_limit(
                bucket="login",
                identity="x",
                limit=1,
                window_seconds=60,
                fail_closed=False,
            )


if __name__ == "__main__":
    unittest.main()
