import unittest

from settings import Settings


class DatabaseSettingsTests(unittest.TestCase):
    def test_database_url_safely_encodes_credentials(self):
        settings = Settings(
            _env_file=None,
            POSTGRES_HOST="localhost",
            POSTGRES_PORT=5432,
            POSTGRES_DB="chess db",
            POSTGRES_USER="chess user",
            POSTGRES_PASSWORD="secret/@value",
            POSTGRES_SSLMODE="require",
        )

        database_url = settings.database_url
        rendered_url = database_url.render_as_string(hide_password=False)

        self.assertEqual(database_url.username, "chess user")
        self.assertEqual(database_url.password, "secret/@value")
        self.assertEqual(database_url.database, "chess db")
        self.assertIn("secret%2F%40value", rendered_url)
        self.assertNotIn("secret/@value", rendered_url)

    def test_missing_credentials_are_reported_without_secret_values(self):
        settings = Settings(
            _env_file=None,
            POSTGRES_HOST="localhost",
            POSTGRES_DB="",
            POSTGRES_USER="",
            POSTGRES_PASSWORD="",
        )

        with self.assertRaisesRegex(
            RuntimeError, "POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD"
        ):
            _ = settings.database_url


if __name__ == "__main__":
    unittest.main()
