import unittest
from typing import cast

from db.base import Base
from db.models import (
    Analysis,
    AnalysisStatus,
    AuditLog,
    AuthSession,
    AuthToken,
    AuthTokenType,
    Bot,
    BotVisibility,
    ChatMessage,
    ChessPlatformAccount,
    Entitlement,
    Game,
    GameSource,
    Identity,
    PaymentOrder,
    PlanGrant,
    SystemRole,
    SupportMessage,
    SupportTicket,
    User,
    UserStatus,
    UsageEvent,
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
                "plan_grants",
                "usage_events",
                "games",
                "analyses",
                "chat_messages",
                "chess_platform_accounts",
                "runtime_settings",
                "payment_orders",
                "support_tickets",
                "support_messages",
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
        game_source_type = inspect(Game).columns.source.type
        analysis_status_type = inspect(Analysis).columns.status.type

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
        self.assertEqual(
            cast(Enum, game_source_type).enums, [item.value for item in GameSource]
        )
        self.assertEqual(
            cast(Enum, analysis_status_type).enums,
            [item.value for item in AnalysisStatus],
        )

    def test_games_are_idempotent_per_owner_and_external_source(self):
        game_constraints = {
            constraint.name for constraint in cast(Table, Game.__table__).constraints
        }

        self.assertIn("uq_games_owner_source_external", game_constraints)
        self.assertIn("ck_games_pgn_length", game_constraints)

    def test_chat_messages_are_owned_and_limited_to_supported_roles(self):
        table = cast(Table, ChatMessage.__table__)
        checks = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        }
        self.assertIn("ck_chat_messages_role_allowed", checks)
        self.assertIn("ck_chat_messages_kind_allowed", checks)
        self.assertIn("ck_chat_messages_content_length", checks)
        self.assertIn("ck_chat_messages_message_order_range", checks)

    def test_platform_username_is_unique_per_user_and_provider(self):
        table = cast(Table, ChessPlatformAccount.__table__)
        constraints = {constraint.name for constraint in table.constraints}
        self.assertIn("uq_chess_platform_accounts_user_provider", constraints)
        self.assertIn("ck_chess_platform_accounts_provider_normalized", constraints)

    def test_support_tickets_and_messages_have_bounded_values(self):
        ticket_checks = {
            constraint.name
            for constraint in cast(Table, SupportTicket.__table__).constraints
            if isinstance(constraint, CheckConstraint)
        }
        message_checks = {
            constraint.name
            for constraint in cast(Table, SupportMessage.__table__).constraints
            if isinstance(constraint, CheckConstraint)
        }
        self.assertIn("ck_support_tickets_category_allowed", ticket_checks)
        self.assertIn("ck_support_tickets_status_allowed", ticket_checks)
        self.assertIn("ck_support_tickets_subject_length", ticket_checks)
        self.assertIn("ck_support_messages_author_role_allowed", message_checks)
        self.assertIn("ck_support_messages_content_length", message_checks)

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
        self.assertFalse(inspect(Bot).columns.extra_weakening.nullable)

    def test_entitlements_are_unique_per_user_and_audit_is_append_only(self):
        entitlement_constraints = {
            constraint.name
            for constraint in cast(Table, Entitlement.__table__).constraints
        }
        self.assertIn("uq_entitlements_user_key", entitlement_constraints)
        self.assertNotIn("updated_at", AuditLog.__table__.columns)
        self.assertIn("created_at", AuditLog.__table__.columns)

        plan_checks = {
            constraint.name
            for constraint in cast(Table, PlanGrant.__table__).constraints
            if isinstance(constraint, CheckConstraint)
        }
        usage_checks = {
            constraint.name
            for constraint in cast(Table, UsageEvent.__table__).constraints
            if isinstance(constraint, CheckConstraint)
        }
        self.assertIn("ck_plan_grants_ends_after_start", plan_checks)
        self.assertIn("ck_usage_events_quantity_positive", usage_checks)

    def test_payment_orders_allow_only_one_pending_order_per_user(self):
        table = cast(Table, PaymentOrder.__table__)
        checks = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        }
        pending_index = next(
            index
            for index in table.indexes
            if index.name == "uq_payment_orders_one_pending_per_user"
        )

        self.assertIn("ck_payment_orders_amount_positive", checks)
        self.assertIn("ck_payment_orders_premium_days_range", checks)
        self.assertIn("ck_payment_orders_status_allowed", checks)
        self.assertTrue(pending_index.unique)


if __name__ == "__main__":
    unittest.main()
