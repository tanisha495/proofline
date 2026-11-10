"""Approval & Review Workflow Service with Role-Based Risk Matrix."""
from __future__ import annotations

import uuid
from typing import Any, Dict
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.models.approval import Approval
from app.models.draft import Draft, DraftVersion
from app.models.finding import Finding
from app.models.user import User
from app.services.workflow.receipt_service import generate_claim_receipts


def calculate_risk_tier(db: Session, version_id: uuid.UUID) -> Dict[str, Any]:
    """Calculate role-based risk tier according to the governance matrix."""
    findings = db.scalars(select(Finding).where(Finding.version_id == version_id)).all()

    has_blockers = any(f.severity == "blocker" for f in findings)
    has_warnings = any(f.severity == "warning" for f in findings)

    if has_blockers:
        return {
            "risk_tier": "Level 3: High",
            "required_role": "reviewer",
            "action": "Strict quarantine; mandatory compliance review and sign-off.",
        }
    elif has_warnings:
        return {
            "risk_tier": "Level 2: Medium",
            "required_role": "reviewer",
            "action": "Requires reviewer or manager sign-off.",
        }
    else:
        return {
            "risk_tier": "Level 1: Low",
            "required_role": "creator",
            "action": "Auto-approved or quick peer review.",
        }


def request_human_review(db: Session, draft: Draft, user: User) -> Dict[str, Any]:
    """Submit a draft for human review and assign appropriate risk tier."""
    latest_version = db.scalars(
        select(DraftVersion)
        .where(DraftVersion.draft_id == draft.id)
        .order_by(desc(DraftVersion.version_number))
    ).first()

    risk_info = (
        calculate_risk_tier(db, latest_version.id)
        if latest_version
        else {"risk_tier": "Level 1: Low", "required_role": "creator"}
    )

    draft.status = "in_review"

    log_action(
        db=db,
        organisation_id=draft.organisation_id,
        user_id=user.id,
        action="review_requested",
        entity="draft",
        entity_id=draft.id,
        details={
            "risk_tier": risk_info["risk_tier"],
            "required_role": risk_info["required_role"],
            "version_number": latest_version.version_number if latest_version else 1,
        },
    )
    db.commit()

    return {
        "draft_id": str(draft.id),
        "status": "in_review",
        "risk_tier": risk_info["risk_tier"],
        "required_role": risk_info["required_role"],
    }


def record_approval_decision(
    db: Session,
    draft: Draft,
    user: User,
    decision: str,
    reason: str | None = None,
    override_reason: str | None = None,
) -> Approval:
    """Record an approval or changes-requested decision."""
    latest_version = db.scalars(
        select(DraftVersion)
        .where(DraftVersion.draft_id == draft.id)
        .order_by(desc(DraftVersion.version_number))
    ).first()

    if not latest_version:
        raise ValueError("Draft has no version to approve")

    normalized = decision.strip().lower()
    if normalized in {"approved", "approve"}:
        db_decision = "approved"
        draft.status = "approved"
        generate_claim_receipts(db, draft, latest_version, user)
    else:
        db_decision = "changes_requested"
        draft.status = "changes_requested"

    approval_entry = Approval(
        organisation_id=draft.organisation_id,
        draft_id=draft.id,
        version_id=latest_version.id,
        reviewer_id=user.id,
        decision=db_decision,
        override_reason=override_reason,
        note=reason,
    )
    db.add(approval_entry)
    db.flush()

    log_action(
        db=db,
        organisation_id=draft.organisation_id,
        user_id=user.id,
        action=f"draft_{db_decision}",
        entity="approval",
        entity_id=approval_entry.id,
        details={
            "draft_id": str(draft.id),
            "decision": db_decision,
            "reason": reason,
        },
    )
    db.commit()
    db.refresh(approval_entry)

    return approval_entry
