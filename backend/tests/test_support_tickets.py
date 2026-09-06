import unittest

from main import app
from pydantic import ValidationError
from support.schemas import TicketCreate, TicketMessageCreate


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


class SupportRouteSecurityTests(unittest.TestCase):
    def test_user_support_reads_require_session(self):
        paths = app.openapi()["paths"]
        for path in (
            "/api/support/unread-count",
            "/api/support/tickets",
            "/api/support/tickets/{ticket_id}",
        ):
            self.assertIn({"SessionCookie": []}, paths[path]["get"].get("security", []))

    def test_user_support_writes_require_csrf(self):
        paths = app.openapi()["paths"]
        for path, method in (
            ("/api/support/tickets", "post"),
            ("/api/support/tickets/{ticket_id}/messages", "post"),
            ("/api/support/tickets/{ticket_id}/read", "post"),
        ):
            operation = paths[path][method]
            self.assertIn({"SessionCookie": []}, operation.get("security", []))
            self.assertTrue(
                any(
                    parameter["name"] == "X-CSRF-Token"
                    for parameter in operation.get("parameters", [])
                )
            )


if __name__ == "__main__":
    unittest.main()
