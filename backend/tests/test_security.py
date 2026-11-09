from datetime import datetime, timezone

import pytest
from jwt.exceptions import PyJWTError

from app.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hashing_uses_non_reversible_hash() -> None:
    password = "strong example passphrase"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("not the passphrase", hashed)


def test_invalid_access_token_is_rejected() -> None:
    with pytest.raises(PyJWTError):
        decode_access_token("not-a-signed-token")


def test_access_tokens_have_unique_revocation_identifiers() -> None:
    first = decode_access_token(create_access_token(12))
    second = decode_access_token(create_access_token(12))

    assert first.user_id == 12
    assert first.token_id
    assert first.token_id != second.token_id
    assert first.expires_at > datetime.now(timezone.utc)
