"""Claim Receipt Service: Generates immutable evidence receipts upon approval."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.claim_receipt import Claim, ClaimReceipt
from app.models.draft import Draft, DraftVersion
from app.models.finding import Finding
from app.models.source import GuidelineRule
from app.models.user import User


def generate_claim_receipts(
    db: Session,
    draft: Draft,
    version: DraftVersion,
    approved_by: User,
) -> List[ClaimReceipt]:
    """Generate and persist the immutable Claim Receipt for an approved draft version."""
    existing = db.scalars(
        select(ClaimReceipt).where(ClaimReceipt.version_id == version.id)
    ).first()
    if existing:
        return [existing]

    claims = db.scalars(select(Claim).where(Claim.version_id == version.id)).all()
    findings = db.scalars(select(Finding).where(Finding.version_id == version.id)).all()
    rules = db.scalars(
        select(GuidelineRule).where(
            GuidelineRule.organisation_id == draft.organisation_id,
            GuidelineRule.is_active == True,  # noqa: E712
        )
    ).all()

    approval_ts = datetime.now(timezone.utc)

    claims_snapshot = {
        "draft_id": str(draft.id),
        "version_number": version.version_number,
        "approved_by_email": approved_by.email,
        "approved_by_role": approved_by.role,
        "approval_timestamp": approval_ts.isoformat(),
        "integrity_motto": "Every claim linked to its proof. No source, no flag.",
        "claims": [
            {
                "id": str(c.id),
                "claim_text": c.claim_text,
                "status": c.status,
                "evidence_fact_key": c.evidence_fact_key,
                "evidence_version": c.evidence_version,
            }
            for c in claims
        ],
    }

    guideline_versions = {r.rule_id: r.version for r in rules}
    override_reasons = [
        {
            "finding_id": str(f.id),
            "source_ref": f.source_ref,
            "reason": f.dismissal_reason,
        }
        for f in findings
        if f.status == "dismissed" and f.dismissal_reason
    ]

    receipt = ClaimReceipt(
        organisation_id=draft.organisation_id,
        draft_id=draft.id,
        version_id=version.id,
        approved_by=approved_by.id,
        approved_at=approval_ts,
        content_hash=version.content_hash,
        claims_snapshot=claims_snapshot,
        guideline_versions=guideline_versions,
        override_reasons=override_reasons,
    )
    db.add(receipt)
    db.flush()
    return [receipt]
