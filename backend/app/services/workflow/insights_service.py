"""Guideline Health & Insights Analytics Service."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finding import Finding
from app.models.source import GuidelineRule


def get_rule_insights(db: Session, organisation_id: uuid.UUID) -> List[Dict[str, Any]]:
    """Aggregate rule metrics: trigger count, dismissal rate, and Guideline Health Score."""
    rules = db.scalars(
        select(GuidelineRule).where(GuidelineRule.organisation_id == organisation_id)
    ).all()

    findings = db.scalars(
        select(Finding).where(Finding.organisation_id == organisation_id)
    ).all()

    rule_stats: Dict[str, Dict[str, int]] = {}
    for r in rules:
        rule_stats[r.rule_id] = {
            "triggers": 0,
            "accepted": 0,
            "edited": 0,
            "dismissed": 0,
            "open": 0,
        }

    for f in findings:
        ref = f.source_ref
        if ref in rule_stats:
            rule_stats[ref]["triggers"] += 1
            st = f.status.lower()
            if st in rule_stats[ref]:
                rule_stats[ref][st] += 1

    insights_list: List[Dict[str, Any]] = []
    for rule_id, stats in rule_stats.items():
        total = stats["triggers"]
        dismissed = stats["dismissed"]
        accepted_or_edited = stats["accepted"] + stats["edited"]

        if total > 0:
            acceptance_rate = round(accepted_or_edited / total, 2)
            health_score = max(0, round((1.0 - (dismissed / total)) * 100))
        else:
            acceptance_rate = 1.0
            health_score = 100

        insights_list.append(
            {
                "rule_id": rule_id,
                "trigger_count": total,
                "acceptance_rate": acceptance_rate,
                "dismissal_count": dismissed,
                "health_score": health_score,
            }
        )

    return insights_list
