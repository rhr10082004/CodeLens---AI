from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from jwt.exceptions import PyJWTError
from pwdlib import PasswordHash

from app.core.config import get_settings

ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: int
    token_id: str
    expires_at: datetime


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    secret = settings.jwt_secret_key.get_secret_value()
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters.")
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {"sub": str(user_id), "jti": str(uuid4()), "exp": expires},
        secret,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> AccessTokenClaims:
    settings = get_settings()
    secret = settings.jwt_secret_key.get_secret_value()
    if len(secret) < 32:
        raise PyJWTError("Authentication is not configured.")
    payload = jwt.decode(
        token,
        secret,
        algorithms=[ALGORITHM],
        options={"require": ["sub", "jti", "exp"]},
    )
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        raise PyJWTError("Invalid token subject.")
    token_id = payload.get("jti")
    expiration = payload.get("exp")
    if not isinstance(token_id, str) or not token_id or not isinstance(expiration, (int, float)):
        raise PyJWTError("Invalid token claims.")
    return AccessTokenClaims(
        user_id=int(subject),
        token_id=token_id,
        expires_at=datetime.fromtimestamp(expiration, timezone.utc),
    )
