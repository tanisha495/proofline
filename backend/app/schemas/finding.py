"""Finding schema – the shared contract used across backend, frontend and docs.

Field alias note
----------------
The API contract exposes ``start`` and ``end`` as field names (matching the
frontend TypeScript type).  ``end`` is an SQL reserved word, so the database
columns are ``start_offset`` and ``end_offset``.  Pydantic aliases bridge the
gap: the ORM populates ``start_offset``/``end_offset``; the API serialises
them as ``start``/``end``.

When constructing a Finding from request JSON use ``model_validate`` with
``by_alias=True`` (the default for FastAPI request bodies).
When serialising for responses use ``model_dump(by_alias=True)``.
"""
from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator


class FindingBase(BaseModel):
    """Base fields for a Finding (excludes IDs)."""

    quoted_text: str
    # API name: start  →  DB column: start_offset
    start_offset: int = Field(
        ...,
        alias="start",
        validation_alias=AliasChoices("start", "start_offset"),
        serialization_alias="start",
    )
    # API name: end  →  DB column: end_offset
    end_offset: int = Field(
        ...,
        alias="end",
        validation_alias=AliasChoices("end", "end_offset"),
        serialization_alias="end",
    )
    severity: Literal["blocker", "warning", "note"]
    reason: str
    source_ref: str = Field(..., min_length=1)
    source_version: int
    confidence: Literal["high", "medium", "low"]
    suggestion: str | None = None
    status: Literal["open", "accepted", "edited", "dismissed"] = "open"
    dismissal_reason: str | None = None

    @field_validator("source_ref")
    @classmethod
    def source_ref_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source_ref must not be empty")
        return v

    model_config = {"populate_by_name": True}


class Finding(FindingBase):
    """Full Finding with identifiers."""

    id: str
    draft_id: str
    version_id: str

    model_config = {"from_attributes": True, "populate_by_name": True}


class FindingUpdate(BaseModel):
    """Payload for PATCH /findings/{id}."""

    status: Literal["open", "accepted", "edited", "dismissed"] | None = None
    dismissal_reason: str | None = None
