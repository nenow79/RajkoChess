from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ENV_FILE = Path(__file__).resolve().with_name(".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )

    postgres_host: str = Field(default="", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(default="", validation_alias="POSTGRES_DB")
    postgres_user: str = Field(default="", validation_alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(
        default=SecretStr(""), validation_alias="POSTGRES_PASSWORD"
    )
    postgres_sslmode: str = Field(default="prefer", validation_alias="POSTGRES_SSLMODE")
    postgres_connect_timeout: int = Field(
        default=5, ge=1, le=30, validation_alias="POSTGRES_CONNECT_TIMEOUT"
    )
    auth_cookie_name: str = Field(
        default="rajko_session", validation_alias="AUTH_COOKIE_NAME"
    )
    auth_csrf_cookie_name: str = Field(
        default="rajko_csrf", validation_alias="AUTH_CSRF_COOKIE_NAME"
    )
    auth_cookie_secure: bool = Field(
        default=False, validation_alias="AUTH_COOKIE_SECURE"
    )
    auth_session_idle_days: int = Field(
        default=7, gt=0, validation_alias="AUTH_SESSION_IDLE_DAYS"
    )
    auth_session_absolute_days: int = Field(
        default=30, gt=0, validation_alias="AUTH_SESSION_ABSOLUTE_DAYS"
    )
    public_app_url: str = Field(
        default="http://localhost:5173", validation_alias="PUBLIC_APP_URL"
    )
    google_oauth_client_id: str = Field(
        default="", validation_alias="GOOGLE_OAUTH_CLIENT_ID"
    )
    google_oauth_client_secret: SecretStr = Field(
        default=SecretStr(""), validation_alias="GOOGLE_OAUTH_CLIENT_SECRET"
    )
    google_oauth_redirect_uri: str = Field(
        default="http://localhost:5173/api/auth/google/callback",
        validation_alias="GOOGLE_OAUTH_REDIRECT_URI",
    )
    smtp_host: str = Field(default="smtp.mail.ovh.net", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=465, gt=0, le=65535, validation_alias="SMTP_PORT")
    smtp_username: str = Field(default="", validation_alias="SMTP_USERNAME")
    smtp_password: SecretStr = Field(
        default=SecretStr(""), validation_alias="SMTP_PASSWORD"
    )
    smtp_from_email: str = Field(default="", validation_alias="SMTP_FROM_EMAIL")
    smtp_from_name: str = Field(
        default="Rajko Chess", validation_alias="SMTP_FROM_NAME"
    )
    email_verification_hours: int = Field(
        default=24, gt=0, le=168, validation_alias="EMAIL_VERIFICATION_HOURS"
    )
    password_reset_minutes: int = Field(
        default=60, gt=0, le=1440, validation_alias="PASSWORD_RESET_MINUTES"
    )
    manual_payment_recipient: str = Field(
        default="", max_length=160, validation_alias="MANUAL_PAYMENT_RECIPIENT"
    )
    manual_payment_iban: str = Field(
        default="", max_length=34, validation_alias="MANUAL_PAYMENT_IBAN"
    )
    manual_premium_amount_grosze: int = Field(
        default=1000,
        ge=100,
        le=1_000_000,
        validation_alias="MANUAL_PREMIUM_AMOUNT_GROSZE",
    )
    manual_premium_days: int = Field(
        default=30, ge=1, le=366, validation_alias="MANUAL_PREMIUM_DAYS"
    )
    redis_url: str = Field(
        default="redis://127.0.0.1:6379/0", validation_alias="REDIS_URL"
    )
    global_engine_concurrency: int = Field(
        default=2, ge=1, le=32, validation_alias="GLOBAL_ENGINE_CONCURRENCY"
    )
    global_full_analysis_concurrency: int = Field(
        default=1,
        ge=1,
        le=16,
        validation_alias="GLOBAL_FULL_ANALYSIS_CONCURRENCY",
    )
    global_llm_concurrency: int = Field(
        default=2, ge=1, le=32, validation_alias="GLOBAL_LLM_CONCURRENCY"
    )
    global_external_api_concurrency: int = Field(
        default=4,
        ge=1,
        le=64,
        validation_alias="GLOBAL_EXTERNAL_API_CONCURRENCY",
    )
    rate_limit_key_secret: SecretStr = Field(
        default=SecretStr("local-development-rate-limit-secret"),
        validation_alias="RATE_LIMIT_KEY_SECRET",
    )
    openrouter_timeout_seconds: float = Field(
        default=60,
        ge=10,
        le=180,
        validation_alias="OPENROUTER_TIMEOUT_SECONDS",
    )
    openrouter_max_retries: int = Field(
        default=1, ge=0, le=2, validation_alias="OPENROUTER_MAX_RETRIES"
    )
    openrouter_position_max_tokens: int = Field(
        default=800,
        ge=200,
        le=1200,
        validation_alias="OPENROUTER_POSITION_MAX_TOKENS",
    )
    openrouter_game_max_tokens: int = Field(
        default=1200,
        ge=400,
        le=1800,
        validation_alias="OPENROUTER_GAME_MAX_TOKENS",
    )
    openrouter_translation_max_tokens: int = Field(
        default=1400,
        ge=400,
        le=1800,
        validation_alias="OPENROUTER_TRANSLATION_MAX_TOKENS",
    )

    @field_validator("manual_payment_recipient")
    @classmethod
    def normalize_manual_payment_recipient(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("manual_payment_iban")
    @classmethod
    def normalize_manual_payment_iban(cls, value: str) -> str:
        normalized = "".join(value.split()).upper()
        if normalized and (not normalized.startswith("PL") or len(normalized) != 28):
            raise ValueError("MANUAL_PAYMENT_IBAN musi być polskim IBAN-em: PL i 26 cyfr")
        if normalized and not normalized[2:].isdigit():
            raise ValueError("MANUAL_PAYMENT_IBAN może zawierać tylko PL i cyfry")
        if normalized:
            checksum_value = int(normalized[4:] + "2521" + normalized[2:4])
            if checksum_value % 97 != 1:
                raise ValueError("MANUAL_PAYMENT_IBAN ma nieprawidłową sumę kontrolną")
        return normalized

    @model_validator(mode="after")
    def validate_auth_cookie_settings(self) -> "Settings":
        if self.auth_session_absolute_days < self.auth_session_idle_days:
            raise ValueError(
                "AUTH_SESSION_ABSOLUTE_DAYS nie może być mniejsze niż "
                "AUTH_SESSION_IDLE_DAYS"
            )
        if self.auth_cookie_name == self.auth_csrf_cookie_name:
            raise ValueError("Cookie sesji i CSRF muszą mieć różne nazwy")
        uses_host_prefix = self.auth_cookie_name.startswith(
            "__Host-"
        ) or self.auth_csrf_cookie_name.startswith("__Host-")
        if uses_host_prefix and not self.auth_cookie_secure:
            raise ValueError(
                "Cookie z prefiksem __Host- wymaga AUTH_COOKIE_SECURE=true"
            )
        rate_secret = self.rate_limit_key_secret.get_secret_value()
        if len(rate_secret) < 32:
            raise ValueError("RATE_LIMIT_KEY_SECRET musi mieć co najmniej 32 znaki")
        if self.auth_cookie_secure and rate_secret == "local-development-rate-limit-secret":
            raise ValueError(
                "Produkcja wymaga własnego losowego RATE_LIMIT_KEY_SECRET"
            )
        self.public_app_url = self.public_app_url.rstrip("/")
        return self

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(
            self.google_oauth_client_id
            and self.google_oauth_client_secret.get_secret_value()
            and self.google_oauth_redirect_uri
        )

    @property
    def manual_payments_enabled(self) -> bool:
        return bool(self.manual_payment_recipient and self.manual_payment_iban)

    def require_google_oauth(self) -> None:
        missing = [
            name
            for name, value in {
                "GOOGLE_OAUTH_CLIENT_ID": self.google_oauth_client_id,
                "GOOGLE_OAUTH_CLIENT_SECRET": self.google_oauth_client_secret.get_secret_value(),
                "GOOGLE_OAUTH_REDIRECT_URI": self.google_oauth_redirect_uri,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError("Brak konfiguracji Google OAuth: " + ", ".join(missing))

    def require_smtp(self) -> None:
        missing = [
            name
            for name, value in {
                "SMTP_USERNAME": self.smtp_username,
                "SMTP_PASSWORD": self.smtp_password.get_secret_value(),
                "SMTP_FROM_EMAIL": self.smtp_from_email,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError("Brak konfiguracji poczty: " + ", ".join(missing))

    @property
    def database_url(self) -> URL:
        values = {
            "POSTGRES_HOST": self.postgres_host,
            "POSTGRES_DB": self.postgres_db,
            "POSTGRES_USER": self.postgres_user,
            "POSTGRES_PASSWORD": self.postgres_password.get_secret_value(),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise RuntimeError(
                "Brak wymaganej konfiguracji PostgreSQL: " + ", ".join(missing)
            )

        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
            query={
                "sslmode": self.postgres_sslmode,
                "connect_timeout": str(self.postgres_connect_timeout),
            },
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
