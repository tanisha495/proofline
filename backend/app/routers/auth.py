"""Authentication router for ProofLine API."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_dummy_password, verify_password
from app.db import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    role: str
    organisation_id: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate a user and receive a JWT access token.

    Always returns 401 with 'Invalid email or password' on any authentication failure.
    Runs a dummy constant-time verification when email is unknown to prevent timing attacks.
    """
    email = req.email.strip().lower()
    user = db.scalars(select(User).where(User.email == email)).first()

    if not user:
        # Unknown email: perform dummy bcrypt computation for timing resistance
        verify_dummy_password(req.password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check password and active status
    is_password_valid = verify_password(req.password, user.password_hash)
    if not is_password_valid or not user.is_active:
        # Log failure for known organisation, user_id=None
        log_action(
            db=db,
            organisation_id=user.organisation_id,
            user_id=None,
            action="login_failed",
            entity="user",
            entity_id=user.id,
            details={"email": email},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Success: log action and issue token
    log_action(
        db=db,
        organisation_id=user.organisation_id,
        user_id=user.id,
        action="login_success",
        entity="user",
        entity_id=user.id,
        details={"email": email},
    )
    db.commit()

    token = create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "organisation_id": str(user.organisation_id),
        },
    }


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user profile."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "organisation_id": str(current_user.organisation_id),
    }
