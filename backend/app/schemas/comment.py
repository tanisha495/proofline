"""Comment schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CommentCreate(BaseModel):
    text: str
    range_start: int | None = None
    range_end: int | None = None


class Comment(BaseModel):
    id: str
    draft_id: str
    user_id: str
    organisation_id: str
    text: str
    range_start: int | None = None
    range_end: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

