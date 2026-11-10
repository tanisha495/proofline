"""Draft and DraftVersion schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DraftBase(BaseModel):
    channel: str | None = None


class DraftCreate(DraftBase):
    content: str


class Draft(DraftBase):
    id: str
    organisation_id: str
    created_by: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DraftVersion(BaseModel):
    id: str
    draft_id: str
    version_number: int
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}

