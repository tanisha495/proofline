"""Security utilities for ProofLine API: password hashing and JWT management."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.config import settings

# Pre-computed dummy hash to mitigate timing attacks on unknown email lookup
_DUMMY_SALT = bcrypt.gensalt()
_DUMMY_HASH = bcrypt.hashpw(b"proofline_timing_dummy_password_constant_time", _DUMMY_SALT).decode("utf-8")

PLACEHOLDER_SECRETS = {
    "change-me-in-production",
    "proofline-super-secret-jwt-key-2026-secure",
    "",
}


def validate_jwt_secret() -> None:
    """Validate that JWT_SECRET is properly configured on startup.

    Refuse to run if JWT_SECRET is empty or still the placeholder value from
    .env.example, unless ENVIRONMENT=development is true.
    """
    env = getattr(settings, "environment", "development").strip().lower()
    secret = getattr(settings, "jwt_secret", "").strip()

    if env != "development":
        if not secret or secret in PLACEHOLDER_SECRETS:
            raise RuntimeError(
                "Refusing to start: JWT_SECRET is empty or set to an insecure placeholder value. "
                "Set a secure JWT_SECRET in production or set ENVIRONMENT=development."
            )


def hash_password(plain: str) -> str:
    """Hash a password securely using bcrypt directly."""
    pw_bytes = plain.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def verify_dummy_password(plain: str) -> bool:
    """Run a constant-time bcrypt verification when user is not found."""
    return verify_password(plain, _DUMMY_HASH)


def create_access_token(user: Any) -> str:
    """Create a signed JWT access token.

    Claims:
      - sub: user id
      - org: user organisation_id
      - role: user role
      - iat: issued-at timestamp
      - exp: expiration timestamp
    """
    now = datetime.now(timezone.utc)
    expire_minutes = getattr(settings, "jwt_expire_minutes", 60)
    expire = now + timedelta(minutes=expire_minutes)

    user_id = str(getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else ""))
    org_id = str(getattr(user, "organisation_id", None) or (user.get("organisation_id") if isinstance(user, dict) else ""))
    role = str(getattr(user, "role", None) or (user.get("role") if isinstance(user, dict) else ""))

    payload: Dict[str, Any] = {
        "sub": user_id,
        "org": org_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token.

    Invalid, expired or tampered tokens raise HTTP 401.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"verify_exp": True, "verify_signature": True},
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired or tampered token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
