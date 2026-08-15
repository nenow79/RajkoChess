from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
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
