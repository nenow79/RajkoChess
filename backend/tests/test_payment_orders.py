import unittest
import uuid
from datetime import datetime, timezone

from billing.router import payment_order_response
from db.models import PaymentOrder


class PaymentOrderResponseTests(unittest.TestCase):
    def setUp(self):
        self.order = PaymentOrder(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            reference_code="RC-1234567890",
            amount_minor=1000,
            currency="PLN",
            premium_days=30,
            recipient="Jan Kowalski",
            iban="PL61109010140000071219812874",
            status="cancelled",
            created_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
            admin_note="Wewnętrzna notatka administratora",
        )

    def test_owner_response_does_not_expose_admin_note(self):
        response = payment_order_response(self.order)

        self.assertNotIn("admin_note", response)

    def test_admin_response_includes_email_and_note(self):
        response = payment_order_response(
            self.order, email="user@example.com", include_admin=True
        )

        self.assertEqual(response["user_email"], "user@example.com")
        self.assertEqual(response["admin_note"], self.order.admin_note)


if __name__ == "__main__":
    unittest.main()
