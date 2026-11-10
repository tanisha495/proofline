"""Claim and ClaimReceipt schemas."""

from __future__ import annotations

import enum

from pydantic import BaseModel


class ClaimStatus(str, enum.Enum):
    SUPPORTED = "supported"
    CONFLICTS = "conflicts"
    EXPIRED_EVIDENCE = "expired_evidence"
    UNSUPPORTED = "unsupported"
    NEEDS_HUMAN = "needs_human"


class Claim(BaseModel):
    id: str
    draft_id: str
    version_id: str
    organisation_id: str
    quoted_text: str
    status: ClaimStatus
    source_ref: str | None = None

    model_config = {"from_attributes": True}


class ClaimReceipt(BaseModel):
    id: str
    claim_id: str
    organisation_id: str
    receipt_data: dict | None = None

    model_config = {"from_attributes": True}

