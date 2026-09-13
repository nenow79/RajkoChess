import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from db.models import SupportMessage, SupportTicket
from main import app
from pydantic import ValidationError
from support.schemas import (
    AdminTicketCreate,
    AnnouncementCreate,
    TicketCreate,
    TicketMessageCreate,
)
from support.service import WELCOME_KEY, ensure_welcome_thread


class SupportSchemaTests(unittest.TestCase):
    def test_ticket_text_is_trimmed_and_bounded(self):
        payload = TicketCreate(
            category="idea",
            subject="  Lepszy trening  ",
            message="  Dodajmy powtórki błędów.  ",
        )
        self.assertEqual(payload.subject, "Lepszy trening")
        self.assertEqual(payload.message, "Dodajmy powtórki błędów.")

        with self.assertRaises(ValidationError):
            TicketCreate(category="problem", subject="     ", message="Opis")
        with self.assertRaises(ValidationError):
            TicketMessageCreate(message="   ")

    def test_category_is_restricted(self):
        with self.assertRaises(ValidationError):
            TicketCreate(category="spam", subject="Nieznana kategoria", message="Opis")  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            TicketCreate(
                category="message",  # pyright: ignore[reportArgumentType]
                subject="Podszywanie się pod administratora",
                message="Opis",
            )

    def test_admin_messages_and_announcements_are_bounded(self):
        target = uuid.uuid4()
        direct = AdminTicketCreate(
            user_id=target,
            subject="  Informacja o koncie  ",
            message="  Napisz, jeśli masz pytania.  ",
        )
        self.assertEqual(direct.subject, "Informacja o koncie")
        self.assertEqual(direct.message, "Napisz, jeśli masz pytania.")

        announcement = AnnouncementCreate(
            title="  Nowa analiza partii  ",
            content="  Ulepszyliśmy analizę.  ",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        self.assertEqual(announcement.title, "Nowa analiza partii")
        with self.assertRaises(ValidationError):
            AnnouncementCreate(
                title="Wygasłe ogłoszenie",
                content="Treść",
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            )


class SupportRouteSecurityTests(unittest.TestCase):
    def test_user_support_reads_require_session(self):
        paths = app.openapi()["paths"]
        for path in (
            "/api/support/unread-count",
            "/api/support/tickets",
            "/api/support/tickets/{ticket_id}",
            "/api/support/announcements",
        ):
            self.assertIn({"SessionCookie": []}, paths[path]["get"].get("security", []))

    def test_user_support_writes_require_csrf(self):
        paths = app.openapi()["paths"]
        for path, method in (
            ("/api/support/tickets", "post"),
            ("/api/support/tickets/{ticket_id}/messages", "post"),
            ("/api/support/tickets/{ticket_id}/read", "post"),
            ("/api/support/announcements/{announcement_id}/read", "post"),
            ("/api/support/announcements/{announcement_id}/reply", "post"),
        ):
            operation = paths[path][method]
            self.assertIn({"SessionCookie": []}, operation.get("security", []))
            self.assertTrue(
                any(
                    parameter["name"] == "X-CSRF-Token"
                    for parameter in operation.get("parameters", [])
                )
            )

    def test_admin_outbound_routes_require_admin_session_and_csrf(self):
        paths = app.openapi()["paths"]
        for path in (
            "/api/admin/support/tickets",
            "/api/admin/support/announcements",
            "/api/admin/support/announcements/{announcement_id}/archive",
        ):
            operation = paths[path]["post"]
            self.assertIn({"SessionCookie": []}, operation.get("security", []))
            self.assertTrue(
                any(
                    parameter["name"] == "X-CSRF-Token"
                    for parameter in operation.get("parameters", [])
                )
            )


class WelcomeMessageTests(unittest.IsolatedAsyncioTestCase):
    async def test_welcome_thread_is_created_once_as_an_unread_admin_message(self):
        owner_id = uuid.uuid4()
        db = SimpleNamespace(
            scalar=AsyncMock(return_value=None),
            add=Mock(),
            flush=AsyncMock(),
        )

        ticket = await ensure_welcome_thread(
            db, user=SimpleNamespace(id=owner_id)  # type: ignore[arg-type]
        )

        self.assertIsInstance(ticket, SupportTicket)
        self.assertEqual(ticket.owner_id, owner_id)
        self.assertEqual(ticket.category, "message")
        self.assertEqual(ticket.initiated_by, "system")
        self.assertEqual(ticket.welcome_key, WELCOME_KEY)
        self.assertIsNone(ticket.user_last_read_at)
        added_messages = [
            call.args[0]
            for call in db.add.call_args_list
            if isinstance(call.args[0], SupportMessage)
        ]
        self.assertEqual(len(added_messages), 1)
        self.assertEqual(added_messages[0].author_role, "admin")

        db.add.reset_mock()
        db.scalar.return_value = ticket
        repeated = await ensure_welcome_thread(
            db, user=SimpleNamespace(id=owner_id)  # type: ignore[arg-type]
        )
        self.assertIs(repeated, ticket)
        db.add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
