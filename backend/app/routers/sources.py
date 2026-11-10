"""Sources router – guidelines, facts, terminology."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.roles import require_role
from app.db import get_db
from app.models.source import Fact, GuidelineRule, Term
from app.models.user import User
from app.services.workflow.seed_service import seed_sample_data

router = APIRouter(prefix="/sources", tags=["sources"])


class GuidelineCreate(BaseModel):
    rule_id: str
    text: str
    category: Optional[str] = None


class FactCreate(BaseModel):
    statement: str
    fact_key: Optional[str] = None
    value: Optional[str] = None
    owner: Optional[str] = None
    source: Optional[str] = None
    expires_on: Optional[date] = None


class TermCreate(BaseModel):
    term: str
    preferred: Optional[str] = None
    banned: bool = False
    notes: Optional[str] = None


@router.get("")
async def list_sources(
    current_user: User = Depends(require_role("creator", "reviewer", "admin")),
    db: Session = Depends(get_db),
):
    """List all active sources (guidelines, facts, terminology) for the organisation."""
    org_id = current_user.organisation_id

    guidelines = db.scalars(
        select(GuidelineRule).where(
            GuidelineRule.organisation_id == org_id,
            GuidelineRule.is_active == True,  # noqa: E712
        )
    ).all()

    facts = db.scalars(
        select(Fact).where(
            Fact.organisation_id == org_id,
            Fact.is_active == True,  # noqa: E712
        )
    ).all()

    terms = db.scalars(
        select(Term).where(
            Term.organisation_id == org_id,
            Term.is_active == True,  # noqa: E712
        )
    ).all()

    return {
        "guidelines": [
            {
                "id": str(g.id),
                "rule_id": g.rule_id,
                "text": g.rule_text,
                "category": g.category,
                "version": g.version,
                "is_active": g.is_active,
            }
            for g in guidelines
        ],
        "facts": [
            {
                "id": str(f.id),
                "fact_key": f.fact_key,
                "statement": f.statement,
                "value": f.value,
                "owner": f.owner,
                "source": f.source,
                "expires_on": f.expires_on.isoformat() if f.expires_on else None,
                "version": f.version,
            }
            for f in facts
        ],
        "terms": [
            {
                "id": str(t.id),
                "term": t.term,
                "preferred": t.preferred,
                "banned": t.banned,
                "notes": t.notes,
                "version": t.version,
            }
            for t in terms
        ],
    }


@router.post("/guidelines", status_code=status.HTTP_201_CREATED)
async def create_guideline(
    req: GuidelineCreate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Upload or create a versioned guideline rule for the organisation."""
    org_id = current_user.organisation_id
    latest = db.scalars(
        select(GuidelineRule)
        .where(GuidelineRule.organisation_id == org_id, GuidelineRule.rule_id == req.rule_id)
        .order_by(desc(GuidelineRule.version))
    ).first()

    next_version = (latest.version + 1) if latest else 1
    if latest and latest.is_active:
        latest.is_active = False
        db.flush()

    rule = GuidelineRule(
        organisation_id=org_id,
        rule_id=req.rule_id,
        rule_text=req.text,
        category=req.category,
        version=next_version,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(rule)
    db.flush()

    log_action(
        db=db,
        organisation_id=org_id,
        user_id=current_user.id,
        action="guideline_created",
        entity="guideline_rule",
        entity_id=rule.id,
        details={"rule_id": rule.rule_id, "version": rule.version},
    )
    db.commit()
    db.refresh(rule)

    return {
        "id": str(rule.id),
        "rule_id": rule.rule_id,
        "text": rule.rule_text,
        "category": rule.category,
        "version": rule.version,
        "is_active": rule.is_active,
    }


@router.post("/facts", status_code=status.HTTP_201_CREATED)
async def create_fact(
    req: FactCreate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Upload or create a versioned fact entry for the organisation."""
    org_id = current_user.organisation_id
    f_key = req.fact_key or f"FACT-{uuid.uuid4().hex[:6].upper()}"

    latest = db.scalars(
        select(Fact)
        .where(Fact.organisation_id == org_id, Fact.fact_key == f_key)
        .order_by(desc(Fact.version))
    ).first()

    next_version = (latest.version + 1) if latest else 1
    if latest and latest.is_active:
        latest.is_active = False
        db.flush()

    fact = Fact(
        organisation_id=org_id,
        fact_key=f_key,
        statement=req.statement,
        value=req.value,
        owner=req.owner,
        source=req.source,
        expires_on=req.expires_on,
        version=next_version,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(fact)
    db.flush()

    log_action(
        db=db,
        organisation_id=org_id,
        user_id=current_user.id,
        action="fact_created",
        entity="fact",
        entity_id=fact.id,
        details={"fact_key": fact.fact_key, "statement": fact.statement, "value": fact.value},
    )
    db.commit()
    db.refresh(fact)

    return {
        "id": str(fact.id),
        "fact_key": fact.fact_key,
        "statement": fact.statement,
        "value": fact.value,
        "owner": fact.owner,
        "source": fact.source,
        "expires_on": fact.expires_on.isoformat() if fact.expires_on else None,
        "version": fact.version,
    }


@router.post("/terms", status_code=status.HTTP_201_CREATED)
async def create_term(
    req: TermCreate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Upload or create a versioned terminology entry for the organisation."""
    org_id = current_user.organisation_id
    latest = db.scalars(
        select(Term)
        .where(Term.organisation_id == org_id, Term.term == req.term)
        .order_by(desc(Term.version))
    ).first()

    next_version = (latest.version + 1) if latest else 1
    if latest and latest.is_active:
        latest.is_active = False
        db.flush()

    term_row = Term(
        organisation_id=org_id,
        term=req.term,
        preferred=req.preferred,
        banned=req.banned,
        notes=req.notes,
        version=next_version,
        is_active=True,
    )
    db.add(term_row)
    db.flush()

    log_action(
        db=db,
        organisation_id=org_id,
        user_id=current_user.id,
        action="term_created",
        entity="term",
        entity_id=term_row.id,
        details={"term": term_row.term, "banned": term_row.banned},
    )
    db.commit()
    db.refresh(term_row)

    return {
        "id": str(term_row.id),
        "term": term_row.term,
        "preferred": term_row.preferred,
        "banned": term_row.banned,
        "notes": term_row.notes,
        "version": term_row.version,
    }


@router.post("/seed")
async def seed_sources(
    current_user: User = Depends(require_role("creator", "reviewer", "admin")),
    db: Session = Depends(get_db),
):
    """Seed sample data from sample-data directory into database."""
    return seed_sample_data(db)


@router.get("/rag-search")
async def rag_search(
    query: str,
    top_k: int = 5,
    current_user: User = Depends(require_role("creator", "reviewer", "admin")),
):
    """Search Dhruv's ingested RAG knowledge records for relevant evidence."""
    from app.services.rag.lexical import search_rag_knowledge

    return search_rag_knowledge(query=query, top_k=top_k)
