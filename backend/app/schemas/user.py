"""User schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class UserBase(BaseModel):
    email: str
    role: Literal["creator", "reviewer", "admin"]


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: str
    organisation_id: str
    is_active: bool

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

