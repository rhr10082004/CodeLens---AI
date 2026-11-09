from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = "sqlite:///./codelens.db"
    jwt_secret_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="JWT_SECRET_KEY",
    )
    access_token_minutes: int = Field(default=30, ge=5, le=1440)
    rate_limit_storage_uri: SecretStr = Field(
        default=SecretStr("memory://"),
        validation_alias="RATE_LIMIT_STORAGE_URI",
    )
    cors_origins: str = "http://localhost:5173"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    max_source_bytes: int = Field(default=200_000, ge=1_000, le=1_000_000)
    github_token: SecretStr | None = None
    store_source_by_default: bool = False
    checkstyle_jar: str | None = None
    frontend_node_modules_path: str | None = None

    @field_validator("rate_limit_storage_uri")
    @classmethod
    def validate_rate_limit_storage_uri(cls, value: SecretStr) -> SecretStr:
        uri = value.get_secret_value()
        parsed = urlsplit(uri)
        if parsed.scheme == "memory" and uri == "memory://":
            return value
        if parsed.scheme in {"redis", "rediss"} and parsed.hostname:
            return value
        raise ValueError("RATE_LIMIT_STORAGE_URI must be memory:// or a Redis/Rediss connection URL.")

    @model_validator(mode="after")
    def require_shared_rate_limit_storage_in_production(self) -> "Settings":
        uri = self.rate_limit_storage_uri.get_secret_value()
        if self.environment.casefold() == "production" and not uri.startswith(("redis://", "rediss://")):
            raise ValueError("Production requires RATE_LIMIT_STORAGE_URI to point to a shared Redis service.")
        return self

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
