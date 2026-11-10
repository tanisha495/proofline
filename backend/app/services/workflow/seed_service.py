"""Sample data seeding service for ProofLine."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.roles import Role
from app.core.security import hash_password
from app.models.organisation import Organisation
from app.models.source import Fact, GuidelineRule, Term
from app.models.user import User


def get_or_create_default_org(db: Session) -> Organisation:
    """Retrieve or create the default organisation."""
    org = db.scalars(
        select(Organisation).where(Organisation.name == "ProofLine Demo Org")
    ).first()
    if not org:
        org = Organisation(name="ProofLine Demo Org")
        db.add(org)
        db.commit()
        db.refresh(org)
    return org


def seed_sample_data(db: Session) -> dict:
    """Seed sample guidelines, facts, terminology, and test users."""
    org = get_or_create_default_org(db)

    # 1. Seed Demo Users (including both API demo accounts and Tanisha UI demo accounts)
    demo_users = [
        ("admin@proofline.ai", "admin12345", Role.ADMIN.value, "Brand Admin"),
        ("creator@proofline.ai", "creator12345", Role.CREATOR.value, "Content Creator"),
        ("reviewer@proofline.ai", "reviewer12345", Role.REVIEWER.value, "Compliance Reviewer"),
        ("writer@studionorth.demo", "proofline-demo", Role.CREATOR.value, "Studio North Writer"),
        ("manager@studionorth.demo", "proofline-demo", Role.REVIEWER.value, "Studio North Manager"),
    ]
    created_users = 0
    for email, pw, role, full_name in demo_users:
        existing = db.scalars(select(User).where(User.email == email)).first()
        if not existing:
            u = User(
                organisation_id=org.id,
                email=email,
                password_hash=hash_password(pw),
                full_name=full_name,
                role=role,
                is_active=True,
            )
            db.add(u)
            created_users += 1

    # Locate sample-data directory
    possible_paths = [
        Path("sample-data"),
        Path("../sample-data"),
        Path(__file__).resolve().parents[4] / "sample-data",
    ]
    sample_dir = None
    for p in possible_paths:
        if p.exists() and (p / "guidelines.json").exists():
            sample_dir = p
            break

    seeded_guidelines = 0
    seeded_facts = 0
    seeded_terms = 0

    if sample_dir:
        # 2. Guidelines (Northwind Coffee)
        gl_file = sample_dir / "guidelines.json"
        if gl_file.exists():
            with open(gl_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    existing = db.scalars(
                        select(GuidelineRule).where(
                            GuidelineRule.organisation_id == org.id,
                            GuidelineRule.rule_id == item["rule_id"],
                        )
                    ).first()
                    if not existing:
                        db.add(
                            GuidelineRule(
                                organisation_id=org.id,
                                rule_id=item["rule_id"],
                                category=item.get("category"),
                                rule_text=item["text"],
                                version=1,
                                is_active=True,
                            )
                        )
                        seeded_guidelines += 1

        # 3. Facts (Northwind Coffee)
        facts_file = sample_dir / "facts.json"
        if facts_file.exists():
            with open(facts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for idx, item in enumerate(data, 1):
                    fact_key = item.get("id") or f"FACT-{idx:02d}"
                    existing = db.scalars(
                        select(Fact).where(
                            Fact.organisation_id == org.id,
                            Fact.fact_key == fact_key,
                        )
                    ).first()
                    if not existing:
                        exp = None
                        if item.get("expires_on"):
                            exp = date.fromisoformat(item["expires_on"])
                        db.add(
                            Fact(
                                organisation_id=org.id,
                                fact_key=fact_key,
                                statement=item["statement"],
                                value=str(item.get("value", "")),
                                owner=item.get("owner"),
                                source=item.get("source"),
                                expires_on=exp,
                                version=1,
                                is_active=True,
                            )
                        )
                        seeded_facts += 1

        # 4. Terminology (Northwind Coffee)
        terms_file = sample_dir / "terminology.json"
        if terms_file.exists():
            with open(terms_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    existing = db.scalars(
                        select(Term).where(
                            Term.organisation_id == org.id,
                            Term.term == item["term"],
                        )
                    ).first()
                    if not existing:
                        db.add(
                            Term(
                                organisation_id=org.id,
                                term=item["term"],
                                preferred=item.get("preferred"),
                                banned=item.get("banned", False),
                                notes=item.get("notes"),
                                version=1,
                                is_active=True,
                            )
                        )
                        seeded_terms += 1

        # 5. Also ingest Dhruv's RAG knowledge records (Real Estate / Asteria Greens) if present
        try:
            from app.services.rag.ingestion import load_and_process_knowledge

            rag_records, _ = load_and_process_knowledge()
            for rec in rag_records:
                if rec.category == "guideline":
                    existing = db.scalars(
                        select(GuidelineRule).where(
                            GuidelineRule.organisation_id == org.id,
                            GuidelineRule.rule_id == rec.source_id,
                        )
                    ).first()
                    if not existing:
                        db.add(
                            GuidelineRule(
                                organisation_id=org.id,
                                rule_id=rec.source_id,
                                category=rec.raw_data.get("category", "Real Estate"),
                                rule_text=rec.searchable_text,
                                version=rec.source_version,
                                is_active=True,
                            )
                        )
                        seeded_guidelines += 1
                elif rec.category in {"fact", "amenity", "pricing", "approval"}:
                    existing = db.scalars(
                        select(Fact).where(
                            Fact.organisation_id == org.id,
                            Fact.fact_key == rec.source_id,
                        )
                    ).first()
                    if not existing:
                        exp = None
                        if rec.valid_until:
                            try:
                                exp = date.fromisoformat(rec.valid_until[:10])
                            except ValueError:
                                exp = None
                        db.add(
                            Fact(
                                organisation_id=org.id,
                                fact_key=rec.source_id,
                                statement=rec.raw_data.get("title") or rec.raw_data.get("statement") or rec.source_id,
                                value=str(rec.raw_data.get("value") or rec.searchable_text[:200]),
                                owner=rec.raw_data.get("owner", "Asteria Developers"),
                                source=rec.source_file,
                                expires_on=exp,
                                version=rec.source_version,
                                is_active=True,
                            )
                        )
                        seeded_facts += 1
                elif rec.category == "terminology":
                    term_val = rec.raw_data.get("term") or rec.source_id
                    existing = db.scalars(
                        select(Term).where(
                            Term.organisation_id == org.id,
                            Term.term == term_val,
                        )
                    ).first()
                    if not existing:
                        db.add(
                            Term(
                                organisation_id=org.id,
                                term=term_val,
                                preferred=rec.raw_data.get("preferred_term") or rec.raw_data.get("preferred"),
                                banned=bool(rec.raw_data.get("banned", False)),
                                notes=rec.raw_data.get("rationale") or rec.searchable_text,
                                version=rec.source_version,
                                is_active=True,
                            )
                        )
                        seeded_terms += 1
        except Exception:
            pass

    db.commit()
    return {
        "status": "seeded",
        "created_users": created_users,
        "guidelines": seeded_guidelines,
        "facts": seeded_facts,
        "terms": seeded_terms,
    }
