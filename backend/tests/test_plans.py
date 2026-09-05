import unittest
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from auth.plans import (
    PLAN_DEFINITIONS,
    current_month_start,
    effective_plan,
    ensure_monthly_quota,
)
from auth.limits import ensure_monthly_available, limited_operation
from fastapi import HTTPException
from db.models import PlanGrant, SystemRole, User
from main import app


class PlanDefinitionTests(unittest.TestCase):
    def test_beta_limits_match_accepted_free_and_premium_matrix(self):
        free = PLAN_DEFINITIONS["free"]
        premium = PLAN_DEFINITIONS["premium"]

        self.assertEqual(free.usage_limits["ai_game_review"], 3)
        self.assertEqual(premium.usage_limits["ai_game_review"], 30)
        self.assertEqual(free.usage_limits["ai_chat"], 10)
        self.assertEqual(premium.usage_limits["ai_chat"], 50)
        self.assertEqual(free.resource_limits["custom_bots"], 1)
        self.assertEqual(premium.resource_limits["custom_bots"], 10)
        self.assertEqual(free.usage_limits["ai_bot_commentary"], 0)

    def test_month_boundary_is_utc(self):
        now = datetime(2026, 8, 31, 23, 59, tzinfo=timezone.utc)
        self.assertEqual(
            current_month_start(now), datetime(2026, 8, 1, tzinfo=timezone.utc)
        )

    def test_plan_and_admin_routes_are_protected_in_openapi(self):
        paths = app.openapi()["paths"]
        self.assertIn("/api/auth/plan", paths)
        self.assertIn("/api/admin/users/{user_id}/plan", paths)
        self.assertIn("/api/admin/users/{user_id}/premium", paths)
        self.assertIn("/api/billing/manual", paths)
        self.assertIn("/api/billing/manual/orders", paths)
        for method in ("post", "delete"):
            operation = paths["/api/admin/users/{user_id}/premium"][method]
            parameters = operation.get("parameters", [])
            self.assertTrue(
                any(item["name"] == "X-CSRF-Token" for item in parameters)
            )
        create_order = paths["/api/billing/manual/orders"]["post"]
        self.assertTrue(
            any(
                item["name"] == "X-CSRF-Token"
                for item in create_order.get("parameters", [])
            )
        )


class EffectivePlanTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_active_grant_means_free(self):
        db = AsyncMock()
        db.scalar.return_value = None
        user = User(id=uuid.uuid4(), email="free@example.com")

        plan = await effective_plan(db, user=user)

        self.assertEqual(plan.key, "free")
        self.assertIsNone(plan.expires_at)

    async def test_active_grant_means_premium_until_its_expiry(self):
        now = datetime.now(timezone.utc)
        grant = PlanGrant(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            ends_at=now + timedelta(days=30),
            reason="Beta",
        )
        db = AsyncMock()
        db.scalar.return_value = grant
        user = User(id=grant.user_id, email="premium@example.com")

        plan = await effective_plan(db, user=user, now=now)

        self.assertEqual(plan.key, "premium")
        self.assertEqual(plan.expires_at, grant.ends_at)

    async def test_admin_has_no_monthly_product_limit(self):
        db = AsyncMock()
        db.scalar.side_effect = [None, 999]
        admin = User(
            id=uuid.uuid4(),
            email="admin@example.com",
            system_role=SystemRole.ADMIN,
        )

        used, limit = await ensure_monthly_quota(
            db, user=admin, key="ai_game_review"
        )

        self.assertEqual(used, 999)
        self.assertIsNone(limit)

    async def test_free_commentary_is_rejected_as_premium_feature(self):
        db = AsyncMock()
        db.scalar.side_effect = [None, 0]
        user = User(id=uuid.uuid4(), email="free@example.com")

        with self.assertRaises(HTTPException) as error:
            await ensure_monthly_available(
                db, user=user, key="ai_bot_commentary"
            )

        self.assertEqual(error.exception.status_code, 429)
        self.assertIn("Premium", error.exception.detail)

    async def test_limited_operation_persists_llm_usage_details(self):
        @asynccontextmanager
        async def available_slot(**_kwargs):
            yield

        db = AsyncMock()
        user = User(id=uuid.uuid4(), email="metrics@example.com")
        record = AsyncMock()
        with (
            patch(
                "auth.limits.effective_plan",
                new=AsyncMock(return_value=SimpleNamespace(key="free")),
            ),
            patch("auth.limits.enforce_rate_limit", new=AsyncMock()),
            patch(
                "auth.limits.ensure_monthly_quota",
                new=AsyncMock(return_value=(0, 10)),
            ),
            patch("auth.limits.concurrency_slot", new=available_slot),
            patch("auth.limits.global_concurrency_slot", new=available_slot),
            patch("auth.limits.record_usage", new=record),
        ):
            async with limited_operation(
                db,
                user=user,
                operation="ai_chat",
                monthly_key="ai_chat",
                concurrency_group="full_analysis",
            ) as details:
                details.update({"total_tokens": 150, "openrouter_cost_credits": 0.1})

        record.assert_awaited_once_with(
            db,
            user=user,
            key="ai_chat",
            details={"total_tokens": 150, "openrouter_cost_credits": 0.1},
        )


if __name__ == "__main__":
    unittest.main()
