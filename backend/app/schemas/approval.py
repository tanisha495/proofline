"""Approval schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ApprovalCreate(BaseModel):
    decision: str
    reason: str | None = None


class Approval(BaseModel):
    id: str
    draft_id: str
    user_id: str
    organisation_id: str
    decision: str
    reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

