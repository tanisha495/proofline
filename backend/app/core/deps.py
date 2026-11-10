"""Authentication and authorization dependencies for ProofLine API."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db import get_db
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract and authenticate the user from JWT bearer token.

    Loads the user from the database. The role and organisation used by the app
    come from the database row, never from the token alone.
    Rejects if user is missing, inactive, or if token org does not match user's organisation.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    token_org = payload.get("org")

    if not user_id or not token_org:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # LOAD USER FROM DATABASE
    user = db.get(User, user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if str(user.organisation_id) != str(token_org):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token organisation mismatch",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(*roles: str):
    """Dependency factory checking that current user's role is in the allowed list."""
    allowed = {r.value if hasattr(r, "value") else str(r) for r in roles}

    def _role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed for your role",
            )
        return user

    return _role_checker


def get_current_org_id(user: User = Depends(get_current_user)) -> uuid.UUID:
    """Return the current user's organisation_id."""
    return user.organisation_id

