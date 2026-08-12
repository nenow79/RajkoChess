import unittest
from typing import cast

from db.base import Base
from db.models import (
    AuditLog,
    AuthSession,
    AuthToken,
    AuthTokenType,
    Bot,
    BotVisibility,
    Entitlement,
    Identity,
    SystemRole,
    User,
    UserStatus,
)
from sqlalchemy import CheckConstraint, Enum, LargeBinary, Table, inspect


class AuthModelMetadataTests(unittest.TestCase):
    def test_all_auth_tables_are_registered(self):
        self.assertEqual(
            set(Base.metadata.tables),
            {
                "users",
                "identities",
                "auth_sessions",
                "auth_tokens",
                "bots",
                "entitlements",
                "audit_log",
            },
        )

    def test_user_email_and_identity_are_unique(self):
        user_constraints = {
            constraint.name for constraint in cast(Table, User.__table__).constraints
        }
        identity_constraints = {
            constraint.name
            for constraint in cast(Table, Identity.__table__).constraints
        }

        self.assertIn("uq_users_email", user_constraints)
        self.assertIn("ck_users_email_normalized", user_constraints)
        self.assertIn("uq_identities_provider_subject", identity_constraints)
        self.assertIn("uq_identities_user_provider", identity_constraints)

    def test_session_and_one_time_tokens_store_only_fixed_length_hashes(self):
        session_table = cast(Table, AuthSession.__table__)
        token_table = cast(Table, AuthToken.__table__)
        self.assertEqual(cast(LargeBinary, session_table.c.token_hash.type).length, 32)
        self.assertEqual(
            cast(LargeBinary, session_table.c.csrf_token_hash.type).length, 32
        )
        self.assertEqual(cast(LargeBinary, token_table.c.token_hash.type).length, 32)

        checks = {
            constraint.name
            for table in (session_table, token_table)
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        }
        self.assertIn("ck_auth_sessions_token_hash_length", checks)
        self.assertIn("ck_auth_tokens_token_hash_length", checks)

    def test_database_enum_values_are_stable_lowercase_identifiers(self):
        mapper = inspect(User)
        status_type = mapper.columns.status.type
        role_type = mapper.columns.system_role.type
        token_type = inspect(AuthToken).columns.type.type

        self.assertIsInstance(status_type, Enum)
        self.assertEqual(
            cast(Enum, status_type).enums, [item.value for item in UserStatus]
        )
        self.assertEqual(
            cast(Enum, role_type).enums, [item.value for item in SystemRole]
        )
        self.assertEqual(
            cast(Enum, token_type).enums, [item.value for item in AuthTokenType]
        )

    def test_bot_visibility_requires_an_owner_only_for_private_bots(self):
        checks = {
            constraint.name
            for constraint in cast(Table, Bot.__table__).constraints
            if isinstance(constraint, CheckConstraint)
        }
        visibility_type = inspect(Bot).columns.visibility.type

        self.assertIn("ck_bots_visibility_owner", checks)
        self.assertIn("ck_bots_target_elo_range", checks)
        self.assertEqual(
            cast(Enum, visibility_type).enums, [item.value for item in BotVisibility]
        )

    def test_entitlements_are_unique_per_user_and_audit_is_append_only(self):
        entitlement_constraints = {
            constraint.name
            for constraint in cast(Table, Entitlement.__table__).constraints
        }
        self.assertIn("uq_entitlements_user_key", entitlement_constraints)
        self.assertNotIn("updated_at", AuditLog.__table__.columns)
        self.assertIn("created_at", AuditLog.__table__.columns)


if __name__ == "__main__":
    unittest.main()
