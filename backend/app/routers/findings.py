"""Findings router."""
from __future__ import annotations

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.roles import require_role
from app.db import get_db
from app.models.finding import Finding
from app.models.user import User

router = APIRouter(prefix="/findings", tags=["findings"])


class FindingUpdate(BaseModel):
    status: Optional[str] = None
    dismissal_reason: Optional[str] = None


@router.patch("/{finding_id}")
async def update_finding(
    finding_id: str,
    req: FindingUpdate,
    current_user: User = Depends(require_role("creator")),
    db: Session = Depends(get_db),
):
    """Update the status or dismissal reason of a finding."""
    try:
        finding_uuid = uuid.UUID(finding_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid finding_id") from exc

    finding = db.get(Finding, finding_uuid)
    if not finding or finding.organisation_id != current_user.organisation_id:
        raise HTTPException(status_code=404, detail="Finding not found")

    new_status = req.status.lower() if req.status else finding.status
    valid_statuses = {"open", "accepted", "edited", "dismissed"}
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of {valid_statuses}",
        )

    new_reason = req.dismissal_reason if req.dismissal_reason is not None else finding.dismissal_reason
    if new_status == "dismissed" and (not new_reason or not new_reason.strip()):
        raise HTTPException(
            status_code=400,
            detail="A dismissal_reason is required when status is 'dismissed'",
        )

    finding.status = new_status
    finding.dismissal_reason = new_reason
    if new_status != "open":
        finding.resolved_by = current_user.id

    db.flush()
    log_action(
        db=db,
        organisation_id=current_user.organisation_id,
        user_id=current_user.id,
        action=f"finding_{finding.status}",
        entity="finding",
        entity_id=finding.id,
        details={
            "source_ref": finding.source_ref,
            "status": finding.status,
            "dismissal_reason": finding.dismissal_reason,
        },
    )
    db.commit()
    db.refresh(finding)

    return {
        "id": str(finding.id),
        "status": finding.status,
        "dismissal_reason": finding.dismissal_reason,
    }
