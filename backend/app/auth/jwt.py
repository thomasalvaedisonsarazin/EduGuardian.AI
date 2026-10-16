"""Access tokens (JWT, PyJWT) and opaque refresh tokens."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt as pyjwt

from app.config import settings
from app.exceptions import UnauthorizedError

ACCESS_TOKEN_TYPE = "access"


def create_access_token(user_id: int, *, expires_delta: timedelta | None = None) -> str:
    """Signed JWT with ``sub`` = user id and ``type`` = "access"."""
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": str(user_id), "type": ACCESS_TOKEN_TYPE, "iat": now, "exp": expire}
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> int:
    """Validate an access token and return the user id. Any problem -> UnauthorizedError."""
    try:
        payload = pyjwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["sub", "exp", "type"]},
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Access token expired") from exc
    except pyjwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid access token") from exc
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise UnauthorizedError("Invalid access token")
    try:
        return int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid access token") from exc


def generate_refresh_token() -> str:
    """Random opaque refresh token (48 bytes, url-safe). Only its hash is stored."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """SHA-256 hex digest used as the stored lookup key for a refresh token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
