import unittest
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock

from auth.audit import write_audit
from auth.dependencies import CurrentAuth
from auth.policies import (
    ENTITLEMENT_DEFINITIONS,
    effective_entitlement,
)
from auth.roles import ensure_admin, is_admin
from db.models import Entitlement, SystemRole, User
from fastapi import HTTPException
from main import app
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class AuthStub:
    user: User


class EntitlementPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_free_defaults_are_independent_of_plan_names(self):
        user = User(id=uuid.uuid4(), email="user@example.com")
        db = AsyncMock()
        db.scalar.return_value = None

        enabled, limit_value, source = await effective_entitlement(
            db, user=user, key="custom_bot"
        )

        self.assertTrue(enabled)
        self.assertIsNone(limit_value)
        self.assertEqual(source, "default")
        self.assertNotIn("free", ENTITLEMENT_DEFINITIONS)
        self.assertNotIn("premium", ENTITLEMENT_DEFINITIONS)

    async def test_manual_override_changes_effective_entitlement(self):
        user = User(id=uuid.uuid4(), email="user@example.com")
        override = Entitlement(
            user_id=user.id,
            key="custom_bot",
            enabled=False,
            limit_value=0,
            source="manual",
        )
        db = AsyncMock()
        db.scalar.return_value = override

        self.assertEqual(
            await effective_entitlement(db, user=user, key="custom_bot"),
            (False, 0, "manual"),
        )

    async def test_admin_bypasses_product_entitlements(self):
        admin = User(
            id=uuid.uuid4(), email="admin@example.com", system_role=SystemRole.ADMIN
        )
        db = AsyncMock()

        self.assertEqual(
            await effective_entitlement(db, user=admin, key="training_plan"),
            (True, None, "admin"),
        )
        db.scalar.assert_not_awaited()


class AuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_audit_entry_identifies_actor_session_resource_and_reason(self):
        user = User(id=uuid.uuid4(), email="admin@example.com")
        session_id = uuid.uuid4()
        current = SimpleNamespace(user=user, session=SimpleNamespace(id=session_id))
        db = SimpleNamespace(add=Mock(), flush=AsyncMock())

        entry = await write_audit(
            cast(AsyncSession, db),
            current=cast(CurrentAuth, current),
            action="bot.admin_inspected",
            resource_type="bot",
            resource_id="resource-id",
            reason="Zgłoszenie użytkownika",
            details={"visibility": "private"},
        )

        self.assertEqual(entry.actor_user_id, user.id)
        self.assertEqual(entry.actor_session_id, session_id)
        self.assertEqual(entry.resource_id, "resource-id")
        self.assertEqual(entry.reason, "Zgłoszenie użytkownika")
        db.add.assert_called_once_with(entry)
        db.flush.assert_awaited_once()


class RolePolicyTests(unittest.TestCase):
    def test_admin_policy_is_centralized(self):
        user = User(id=uuid.uuid4(), email="user@example.com")
        admin = User(
            id=uuid.uuid4(), email="admin@example.com", system_role=SystemRole.ADMIN
        )

        self.assertFalse(is_admin(user))
        self.assertTrue(is_admin(admin))
        self.assertIs(ensure_admin(AuthStub(user=admin)).user, admin)
        with self.assertRaises(HTTPException) as raised:
            ensure_admin(AuthStub(user=user))
        self.assertEqual(raised.exception.status_code, 403)

    def test_admin_mutations_require_csrf_and_admin_cookie(self):
        paths = app.openapi()["paths"]
        for path, method in (
            ("/api/admin/users/{user_id}", "patch"),
            ("/api/admin/users/{user_id}/entitlements/{key}", "put"),
            ("/api/admin/bots/{bot_id}/inspect", "post"),
            ("/api/admin/settings/bot-strength", "put"),
            ("/api/admin/payment-orders/{order_id}/confirm", "post"),
            ("/api/admin/payment-orders/{order_id}/cancel", "post"),
            ("/api/admin/support/tickets/{ticket_id}/messages", "post"),
            ("/api/admin/support/tickets/{ticket_id}/read", "post"),
            ("/api/admin/support/tickets/{ticket_id}/status", "patch"),
        ):
            operation = paths[path][method]
            self.assertIn({"SessionCookie": []}, operation.get("security", []))
            self.assertTrue(
                any(
                    parameter["name"] == "X-CSRF-Token"
                    for parameter in operation.get("parameters", [])
                )
            )

    def test_admin_read_routes_require_session_cookie(self):
        paths = app.openapi()["paths"]
        for path in (
            "/api/admin/users",
            "/api/admin/audit-log",
            "/api/admin/statistics",
            "/api/admin/settings/bot-strength",
            "/api/admin/payment-orders",
            "/api/admin/support/unread-count",
            "/api/admin/support/tickets",
        ):
            self.assertIn({"SessionCookie": []}, paths[path]["get"].get("security", []))

    def test_audit_log_has_no_mutating_api(self):
        operation = app.openapi()["paths"]["/api/admin/audit-log"]
        self.assertEqual(set(operation), {"get"})


if __name__ == "__main__":
    unittest.main()
