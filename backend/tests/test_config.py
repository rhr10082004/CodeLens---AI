import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


def test_production_requires_shared_redis_rate_limit_storage() -> None:
    with pytest.raises(ValidationError, match="Production requires RATE_LIMIT_STORAGE_URI"):
        Settings(environment="production")


@pytest.mark.parametrize("scheme", ["redis", "rediss"])
def test_production_accepts_redis_rate_limit_storage(scheme: str) -> None:
    settings = Settings(
        environment="production",
        rate_limit_storage_uri=SecretStr(f"{scheme}://user:password@redis.example.com:6379/0"),
    )

    assert settings.rate_limit_storage_uri.get_secret_value().startswith(f"{scheme}://")


def test_rate_limit_storage_uri_is_secret_in_repr() -> None:
    settings = Settings(
        rate_limit_storage_uri=SecretStr("redis://user:password@redis.example.com:6379/0"),
    )

    assert "password" not in repr(settings)


def test_rejects_unsupported_rate_limit_storage_uri() -> None:
    with pytest.raises(ValidationError, match="RATE_LIMIT_STORAGE_URI must be"):
        Settings(rate_limit_storage_uri=SecretStr("filesystem:///tmp/limits"))
