"""Source schemas (guidelines, facts, terminology)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class GuidelineRule(BaseModel):
    id: str
    rule_id: str
    text: str
    category: str | None = None
    version: int
    is_active: bool

    model_config = {"from_attributes": True}


class FactEntry(BaseModel):
    id: str
    statement: str
    value: str | None = None
    owner: str | None = None
    source: str | None = None
    expires_on: date | None = None
    version: int

    model_config = {"from_attributes": True}


class TermEntry(BaseModel):
    id: str
    term: str
    preferred: str | None = None
    banned: bool
    notes: str | None = None

    model_config = {"from_attributes": True}

