import unittest

from sqlalchemy import CheckConstraint, Enum, inspect

from db.base import Base
from db.models import (
    AuthSession,
    AuthToken,
    AuthTokenType,
    Identity,
    SystemRole,
    User,
    UserStatus,
)


class AuthModelMetadataTests(unittest.TestCase):
    def test_all_auth_tables_are_registered(self):
        self.assertEqual(
            set(Base.metadata.tables),
            {"users", "identities", "auth_sessions", "auth_tokens"},
        )

    def test_user_email_and_identity_are_unique(self):
        user_constraints = {constraint.name for constraint in User.__table__.constraints}
        identity_constraints = {
            constraint.name for constraint in Identity.__table__.constraints
        }

        self.assertIn("uq_users_email", user_constraints)
        self.assertIn("ck_users_email_normalized", user_constraints)
        self.assertIn("uq_identities_provider_subject", identity_constraints)
        self.assertIn("uq_identities_user_provider", identity_constraints)

    def test_session_and_one_time_tokens_store_only_fixed_length_hashes(self):
        self.assertEqual(AuthSession.__table__.c.token_hash.type.length, 32)
        self.assertEqual(AuthSession.__table__.c.csrf_token_hash.type.length, 32)
        self.assertEqual(AuthToken.__table__.c.token_hash.type.length, 32)

        checks = {
            constraint.name
            for table in (AuthSession.__table__, AuthToken.__table__)
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
        self.assertEqual(status_type.enums, [item.value for item in UserStatus])
        self.assertEqual(role_type.enums, [item.value for item in SystemRole])
        self.assertEqual(token_type.enums, [item.value for item in AuthTokenType])


if __name__ == "__main__":
    unittest.main()
