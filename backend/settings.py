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
            raise ValueError("Cookie z prefiksem __Host- wymaga AUTH_COOKIE_SECURE=true")
        return self

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
            query={"sslmode": self.postgres_sslmode},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
