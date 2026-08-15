import unittest
from unittest.mock import AsyncMock, patch

from main import healthcheck
from fastapi.responses import JSONResponse


class ReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def test_healthcheck_returns_503_when_a_required_service_is_down(self):
        with (
            patch("main.database_healthcheck", new=AsyncMock(return_value=True)),
            patch("main.redis_healthcheck", new=AsyncMock(return_value=False)),
        ):
            response = await healthcheck()

        if not isinstance(response, JSONResponse):
            self.fail("Niegotowy healthcheck powinien zwrócić JSONResponse")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'"status":"unavailable"', response.body)
        self.assertIn(b'"redis":"down"', response.body)

    async def test_healthcheck_reports_all_dependencies_when_ready(self):
        with (
            patch("main.database_healthcheck", new=AsyncMock(return_value=True)),
            patch("main.redis_healthcheck", new=AsyncMock(return_value=True)),
        ):
            response = await healthcheck()

        self.assertEqual(
            response,
            {"status": "ok", "postgres": "ok", "redis": "ok"},
        )


if __name__ == "__main__":
    unittest.main()
