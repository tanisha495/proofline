"""Evaluation script to test ProofLine 4-Layer Review Engine against the sample dataset."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from datetime import datetime
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import (
    Organisation,
    User,
    GuidelineRule,
    Fact,
    Term,
    Draft,
    DraftVersion,
)
from app.services.review.engine import execute_full_review


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    sample_dir = backend_dir.parent / "sample-data"
    guidelines_file = sample_dir / "guidelines.json"
    facts_file = sample_dir / "facts.json"
    terms_file = sample_dir / "terminology.json"
    compliant_draft_file = sample_dir / "seeded-drafts" / "draft_compliant.json"
    seeded_errors_draft_file = sample_dir / "seeded-drafts" / "draft_seeded_errors.json"

    print("======================================================================")
    print("PROOFLINE SAMPLE DATASET EVALUATION")
    print("======================================================================")
    print(f"Loading sample data from: {sample_dir}\n")

    guidelines_data = load_json(guidelines_file)
    facts_data = load_json(facts_file)
    terms_data = load_json(terms_file)
    compliant_data = load_json(compliant_draft_file)
    errors_data = load_json(seeded_errors_draft_file)

    engine = create_engine(settings.database_url, echo=False)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session() as db:
        # 1. Setup Organisation & User
        org = db.scalars(select(Organisation).where(Organisation.name == "Northwind Coffee Evaluation")).first()
        if not org:
            org = Organisation(name="Northwind Coffee Evaluation")
            db.add(org)
            db.commit()
            db.refresh(org)

        user = db.scalars(select(User).where(User.email == "evaluator@proofline.ai")).first()
        if not user:
            user = User(
                organisation_id=org.id,
                email="evaluator@proofline.ai",
                password_hash="test",
                role="creator",
                full_name="Dataset Evaluator",
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # 2. Sync Guidelines
        for g in guidelines_data:
            existing_rule = db.scalars(
                select(GuidelineRule).where(
                    GuidelineRule.organisation_id == org.id,
                    GuidelineRule.rule_id == g["rule_id"]
                )
            ).first()
            if not existing_rule:
                db.add(GuidelineRule(
                    organisation_id=org.id,
                    rule_id=g["rule_id"],
                    category=g.get("category", "General"),
                    text=g["text"],
                    version=1,
                    is_active=True
                ))
            else:
                existing_rule.text = g["text"]
                existing_rule.category = g.get("category", "General")
                existing_rule.is_active = True

        # 3. Sync Facts
        for f in facts_data:
            exp_date = datetime.strptime(f["expires_on"], "%Y-%m-%d").date() if f.get("expires_on") else None
            existing_fact = db.scalars(
                select(Fact).where(
                    Fact.organisation_id == org.id,
                    Fact.statement == f["statement"]
                )
            ).first()
            if not existing_fact:
                db.add(Fact(
                    organisation_id=org.id,
                    fact_key=f.get("id", f["statement"][:20]),
                    statement=f["statement"],
                    value=f["value"],
                    owner=f.get("owner", "Operations"),
                    source=f.get("source", "Archive"),
                    expires_on=exp_date
                ))
            else:
                existing_fact.value = f["value"]
                existing_fact.owner = f.get("owner", "Operations")
                existing_fact.source = f.get("source", "Archive")
                existing_fact.expires_on = exp_date

        # 4. Sync Terminology
        for t in terms_data:
            existing_term = db.scalars(
                select(Term).where(
                    Term.organisation_id == org.id,
                    Term.term == t["term"]
                )
            ).first()
            if not existing_term:
                db.add(Term(
                    organisation_id=org.id,
                    term=t["term"],
                    preferred=t.get("preferred"),
                    banned=t.get("banned", False),
                    notes=t.get("notes")
                ))
            else:
                existing_term.preferred = t.get("preferred")
                existing_term.banned = t.get("banned", False)
                existing_term.notes = t.get("notes")

        db.commit()

        # --------------------------------------------------------------------
        # TEST CASE 1: Compliant Draft (Should pass with 0 blockers)
        # --------------------------------------------------------------------
        print("\n" + "="*70)
        print("TEST CASE 1: Northwind Coffee Compliant Newsletter")
        print("="*70)
        print(f"Content:\n\"{compliant_data['content']}\"\n")

        draft_comp = Draft(
            organisation_id=org.id,
            owner_id=user.id,
            title=compliant_data["name"],
            channel=compliant_data.get("channel", "email_newsletter"),
            status="draft"
        )
        db.add(draft_comp)
        db.commit()
        db.refresh(draft_comp)

        content_comp = compliant_data["content"]
        comp_hash = hashlib.sha256(content_comp.encode("utf-8")).hexdigest()
        version_comp = DraftVersion(
            organisation_id=org.id,
            draft_id=draft_comp.id,
            version_number=1,
            content=content_comp,
            content_hash=comp_hash,
            created_by=user.id,
        )
        db.add(version_comp)
        db.commit()
        db.refresh(version_comp)

        from app.models import Finding, Claim
        results_comp = execute_full_review(db, draft_comp, version_comp, user.id)
        findings_comp = db.scalars(select(Finding).where(Finding.version_id == version_comp.id)).all()
        claims_comp = db.scalars(select(Claim).where(Claim.version_id == version_comp.id)).all()

        print(f"Findings Detected: {len(findings_comp)}")
        print(f"Blocker Count:     {results_comp['blockers_count']} (Expected: {compliant_data.get('expected_blockers', 0)})")
        print(f"Warning Count:     {results_comp['warnings_count']}")
        print(f"Claims Extracted:  {len(claims_comp)}")

        for c in claims_comp:
            print(f"  - Claim: \"{c.claim_text}\" -> Status: {c.status} (Source: {c.evidence_fact_key})")

        comp_passed = (results_comp["blockers_count"] == compliant_data.get("expected_blockers", 0))
        print(f"\nVerdict for Compliant Draft: {'[PASSED] Clean compliance verified' if comp_passed else '[FAILED] Unexpected blockers'}")

        # --------------------------------------------------------------------
        # TEST CASE 2: Draft with Planted Errors
        # --------------------------------------------------------------------
        print("\n" + "="*70)
        print("TEST CASE 2: Northwind Coffee Spring Promotion (Planted Errors)")
        print("="*70)
        print(f"Content:\n\"{errors_data['content']}\"\n")

        draft_err = Draft(
            organisation_id=org.id,
            owner_id=user.id,
            title=errors_data["name"],
            channel=errors_data.get("channel", "social_ad"),
            status="draft"
        )
        db.add(draft_err)
        db.commit()
        db.refresh(draft_err)

        content_err = errors_data["content"]
        err_hash = hashlib.sha256(content_err.encode("utf-8")).hexdigest()
        version_err = DraftVersion(
            organisation_id=org.id,
            draft_id=draft_err.id,
            version_number=1,
            content=content_err,
            content_hash=err_hash,
            created_by=user.id,
        )
        db.add(version_err)
        db.commit()
        db.refresh(version_err)

        results_err = execute_full_review(db, draft_err, version_err, user.id)
        findings_err = db.scalars(select(Finding).where(Finding.version_id == version_err.id)).all()
        claims_err = db.scalars(select(Claim).where(Claim.version_id == version_err.id)).all()

        print(f"Total Findings Generated: {len(findings_err)}")
        print(f"Blockers Detected:        {results_err['blockers_count']}")
        print(f"Warnings Detected:        {results_err['warnings_count']}")
        print(f"Claims Extracted:         {len(claims_err)}")

        print("\n--- DETAILED FINDINGS ---")
        for idx, f in enumerate(findings_err, 1):
            print(f"Finding #{idx}:")
            print(f"  Quoted Text: \"{f.quoted_text}\" (offsets: {f.start_offset}..{f.end_offset})")
            print(f"  Severity:    {f.severity.upper()}")
            print(f"  Source Ref:  {f.source_ref}")
            print(f"  Reason:      {f.reason}")
            print(f"  Suggestion:  {f.suggestion}")
            print()

        # Compare against planted errors
        planted = errors_data.get("planted_errors", [])
        print("--- PLANTED ERROR DETECTION BENCHMARK ---")
        detected_count = 0
        for p in planted:
            p_text = p["quoted_text"]
            p_type = p["type"]
            p_sev = p["expected_severity"]
            
            # Match finding
            matched = False
            for f in findings_err:
                if p_text.lower() in (f.quoted_text or "").lower() or (f.quoted_text or "").lower() in p_text.lower():
                    matched = True
                    print(f"MATCH: Planted [{p_type}] \"{p_text}\" -> Detected as {f.severity.upper()} (Ref: {f.source_ref})")
                    break
            if not matched:
                # Also check claims
                for c in claims_err:
                    if p_text.lower() in (c.claim_text or "").lower() and c.status in ("conflicts", "unsupported", "expired_evidence"):
                        matched = True
                        print(f"MATCH (Claim Ledger): Planted [{p_type}] \"{p_text}\" -> Claim status: {c.status} (Ref: {c.evidence_fact_key})")
                        break
            if matched:
                detected_count += 1
            else:
                print(f"MISSED: Planted [{p_type}] \"{p_text}\"")

        sensitivity = (detected_count / len(planted)) * 100 if planted else 100.0
        print(f"\nDetection Sensitivity: {detected_count}/{len(planted)} ({sensitivity:.1f}%)")
        print("======================================================================\n")


if __name__ == "__main__":
    main()
