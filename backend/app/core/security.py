"""JWT auth + password hashing.

Thin wrapper around `bcrypt` (for password hashing) and `python-jose` (for
JWT encode/decode). Kept in a single module so the rest of the codebase
imports a single facade and can be swapped for Logto / external OAuth
(C2 6.8) without touching every dependency.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"

# bcrypt has a hard 72-byte input limit. We truncate at the boundary so
# very long passwords don't raise.
_BCRYPT_LIMIT = 72


def hash_password(plain: str) -> str:
    raw = plain.encode("utf-8")[:_BCRYPT_LIMIT]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    raw = plain.encode("utf-8")[:_BCRYPT_LIMIT]
    try:
        return bcrypt.checkpw(raw, hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None
