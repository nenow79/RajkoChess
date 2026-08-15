import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from rate_limit import (
    RateLimitStoreUnavailable,
    consume_rate_limit,
    enforce_rate_limit,
    global_concurrency_slot,
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

    async def test_global_semaphore_releases_its_lease(self):
        redis = AsyncMock()
        redis.eval.side_effect = [[1, 0], 1]
        with patch("rate_limit.get_redis", return_value=redis):
            async with global_concurrency_slot(
                bucket="engine", limit=2, ttl_seconds=30
            ):
                pass

        self.assertEqual(redis.eval.await_count, 2)
        acquire_args = redis.eval.await_args_list[0].args
        self.assertEqual(acquire_args[2], "rajko:semaphore:engine")
        self.assertEqual(acquire_args[4:], ("2", "30"))
        release_args = redis.eval.await_args_list[1].args
        self.assertEqual(release_args[2], "rajko:semaphore:engine")
        self.assertEqual(acquire_args[3], release_args[3])

    async def test_global_semaphore_returns_retry_after_when_full(self):
        redis = AsyncMock()
        redis.eval.return_value = [0, 7]
        with (
            patch("rate_limit.get_redis", return_value=redis),
            self.assertRaises(HTTPException) as error,
        ):
            async with global_concurrency_slot(
                bucket="engine", limit=1, ttl_seconds=30
            ):
                pass

        self.assertEqual(error.exception.status_code, 429)
        self.assertEqual(error.exception.headers, {"Retry-After": "7"})


if __name__ == "__main__":
    unittest.main()
