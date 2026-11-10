"""Master Review Engine: Orchestrates the 4-layer review pipeline and persists results."""

import logging
import uuid
from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.models import (
    Claim,
    Draft,
    DraftVersion,
    Fact,
    Finding,
    GuidelineRule,
    Term,
)
from app.schemas.finding import FindingBase
from app.services.review.claim_ledger import process_claim_ledger
from app.services.review.deterministic import run_deterministic_checks
from app.services.review.tone_engine import evaluate_grounded_tone
from app.services.review.validator import validate_and_filter_findings

logger = logging.getLogger(__name__)


def execute_full_review(
    db: Session,
    draft: Draft,
    version: DraftVersion,
    user_id: uuid.UUID | None = None,
) -> Dict[str, Any]:
    """Run the 4-layer review pipeline on a draft version and persist findings & claims."""
    org_id = draft.organisation_id
    content = version.content

    # 1. Fetch sources for organisation
    rules = db.scalars(
        select(GuidelineRule).where(
            GuidelineRule.organisation_id == org_id,
            GuidelineRule.is_active == True,  # noqa: E712
        )
    ).all()

    facts = db.scalars(
        select(Fact).where(Fact.organisation_id == org_id)
    ).all()

    terms = db.scalars(
        select(Term).where(Term.organisation_id == org_id)
    ).all()

    # Compile valid sources for Layer 4 validator
    valid_source_refs = set()
    for r in rules:
        valid_source_refs.add(r.rule_id)
    for f in facts:
        valid_source_refs.add(f.fact_key)
        valid_source_refs.add(f.statement)
        if f.source:
            valid_source_refs.add(f.source)
    for t in terms:
        valid_source_refs.add(f"TERM-{t.term.upper()}")
        valid_source_refs.add(t.term)

    # Layer 1: Deterministic checks (terminology, readability)
    deterministic_findings = run_deterministic_checks(content, list(terms))

    # Layer 2: Claim Ledger (claim extraction & fact verification)
    extracted_claims, claim_findings = process_claim_ledger(content, list(facts))

    # Layer 3: Grounded Tone & Guideline check
    tone_findings = evaluate_grounded_tone(content, list(rules))

    # Combine candidates from Layers 1, 2, and 3
    candidate_findings: List[FindingBase] = (
        deterministic_findings + claim_findings + tone_findings
    )

    # Layer 4: Source Validator ("No source, no flag")
    validated_findings = validate_and_filter_findings(
        findings=candidate_findings,
        content=content,
        valid_source_refs=valid_source_refs,
    )

    # Clear old findings & claims for this specific version to support re-checking
    db.query(Finding).filter(Finding.version_id == version.id).delete()
    db.query(Claim).filter(Claim.version_id == version.id).delete()

    # Persist claims in Claim Ledger table
    persisted_claims = []
    for c in extracted_claims:
        claim_row = Claim(
            organisation_id=org_id,
            version_id=version.id,
            claim_text=c.quoted_text,
            status=c.status.value,
            evidence_fact_key=c.source_ref,
        )
        db.add(claim_row)
        persisted_claims.append(claim_row)

    # Persist validated findings in Finding table
    persisted_findings = []
    blockers_count = 0
    warnings_count = 0

    fact_refs = {f.fact_key for f in facts} | {f.statement for f in facts}
    term_refs = {f"TERM-{t.term.upper()}" for t in terms}

    for vf in validated_findings:
        if vf.severity == "blocker":
            blockers_count += 1
        elif vf.severity == "warning":
            warnings_count += 1

        start_off = max(0, int(vf.start_offset))
        end_off = max(start_off + 1, int(vf.end_offset))

        if vf.source_ref in term_refs or vf.source_ref.startswith("TERM-"):
            s_type = "term"
        elif vf.source_ref in fact_refs or vf.source_ref == "CLAIM-UNSUPPORTED":
            s_type = "fact"
        else:
            s_type = "guideline"

        finding_row = Finding(
            organisation_id=org_id,
            draft_id=draft.id,
            version_id=version.id,
            quoted_text=vf.quoted_text,
            start_offset=start_off,
            end_offset=end_off,
            severity=vf.severity,
            reason=vf.reason,
            source_type=s_type,
            source_ref=vf.source_ref,
            source_version=vf.source_version,
            confidence=vf.confidence,
            suggestion=vf.suggestion,
            status=vf.status,
            dismissal_reason=vf.dismissal_reason,
        )
        db.add(finding_row)
        persisted_findings.append(finding_row)

    db.flush()

    # Audit log entry (flushed in same transaction before commit)
    log_action(
        db=db,
        organisation_id=org_id,
        user_id=user_id,
        action="review_completed",
        entity="draft_version",
        entity_id=version.id,
        details={
            "draft_id": str(draft.id),
            "version_number": version.version_number,
            "findings_count": len(persisted_findings),
            "blockers_count": blockers_count,
            "warnings_count": warnings_count,
            "claims_count": len(persisted_claims),
        },
    )

    # Commit findings, claims, and audit entry together
    db.commit()

    return {
        "draft_id": str(draft.id),
        "version": version.version_number,
        "findings_count": len(persisted_findings),
        "claims_count": len(persisted_claims),
        "blockers_count": blockers_count,
        "warnings_count": warnings_count,
        "status": "reviewed",
    }

