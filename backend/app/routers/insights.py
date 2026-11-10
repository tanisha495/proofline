"""Insights router."""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.roles import require_role
from app.db import get_db
from app.models.user import User
from app.services.workflow.insights_service import get_rule_insights

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/rules")
async def get_rule_performance(
    current_user: User = Depends(require_role("reviewer", "admin")),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get rule performance analytics (most triggered rules, acceptance rates, health scores)."""
    return get_rule_insights(db, current_user.organisation_id)
