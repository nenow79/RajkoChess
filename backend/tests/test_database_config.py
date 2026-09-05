import unittest

from settings import Settings


class DatabaseSettingsTests(unittest.TestCase):
    def test_database_url_safely_encodes_credentials(self):
        settings = Settings.model_validate(
            {
                "POSTGRES_HOST": "localhost",
                "POSTGRES_PORT": 5432,
                "POSTGRES_DB": "chess db",
                "POSTGRES_USER": "chess user",
                "POSTGRES_PASSWORD": "secret/@value",
                "POSTGRES_SSLMODE": "require",
            }
        )

        database_url = settings.database_url
        rendered_url = database_url.render_as_string(hide_password=False)

        self.assertEqual(database_url.username, "chess user")
        self.assertEqual(database_url.password, "secret/@value")
        self.assertEqual(database_url.database, "chess db")
        self.assertEqual(database_url.query["connect_timeout"], "5")
        self.assertIn("secret%2F%40value", rendered_url)
        self.assertNotIn("secret/@value", rendered_url)

    def test_missing_credentials_are_reported_without_secret_values(self):
        settings = Settings.model_validate(
            {
                "POSTGRES_HOST": "localhost",
                "POSTGRES_DB": "",
                "POSTGRES_USER": "",
                "POSTGRES_PASSWORD": "",
            }
        )

        with self.assertRaisesRegex(
            RuntimeError, "POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD"
        ):
            _ = settings.database_url

    def test_manual_payment_configuration_normalizes_polish_iban(self):
        settings = Settings.model_validate(
            {
                "MANUAL_PAYMENT_RECIPIENT": "  Jan   Kowalski ",
                "MANUAL_PAYMENT_IBAN": "PL61 1090 1014 0000 0712 1981 2874",
            }
        )

        self.assertTrue(settings.manual_payments_enabled)
        self.assertEqual(settings.manual_payment_recipient, "Jan Kowalski")
        self.assertEqual(settings.manual_payment_iban, "PL61109010140000071219812874")

    def test_manual_payment_configuration_rejects_invalid_iban_checksum(self):
        with self.assertRaisesRegex(ValueError, "sumę kontrolną"):
            Settings.model_validate(
                {
                    "MANUAL_PAYMENT_RECIPIENT": "Jan Kowalski",
                    "MANUAL_PAYMENT_IBAN": "PL00109010140000071219812874",
                }
            )


if __name__ == "__main__":
    unittest.main()
