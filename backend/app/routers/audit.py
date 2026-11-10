"""Audit router."""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.roles import require_role
from app.db import get_db
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def get_audit_log(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get the immutable audit log entries for the organisation."""
    logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.organisation_id == current_user.organisation_id)
        .order_by(desc(AuditLog.created_at))
        .limit(100)
    ).all()

    return [
        {
            "id": str(log.id),
            "user_id": str(log.user_id) if log.user_id else None,
            "action": log.action,
            "entity": log.entity,
            "entity_id": str(log.entity_id) if log.entity_id else None,
            "details": log.details or {},
            "created_at": log.created_at,
        }
        for log in logs
    ]
