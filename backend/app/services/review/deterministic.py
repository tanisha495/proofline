"""Layer 1: Deterministic review engine (Terminology & Readability)."""

import re
from typing import List
import textstat

from app.models.source import Term
from app.schemas.finding import FindingBase


def run_deterministic_checks(content: str, terms: List[Term]) -> List[FindingBase]:
    """Execute fast rule-based checks: banned terms, preferred substitutions, readability."""
    findings: List[FindingBase] = []

    # 1. Terminology checks
    for t in terms:
        pattern = r"\b" + re.escape(t.term) + r"\b"
        for match in re.finditer(pattern, content, flags=re.IGNORECASE):
            start = match.start()
            end = match.end()
            matched_text = content[start:end]

            if t.banned:
                # Banned term is a blocker
                findings.append(
                    FindingBase(
                        quoted_text=matched_text,
                        start=start,
                        end=end,
                        severity="blocker",
                        reason=f"Banned brand term '{matched_text}' detected. {t.notes or ''}".strip(),
                        source_ref=f"TERM-{t.term.upper()}",
                        source_version=1,
                        confidence="high",
                        suggestion=f"Replace '{matched_text}' with '{t.preferred}'" if t.preferred else f"Remove '{matched_text}'",
                        status="open",
                    )
                )
            elif t.preferred and t.preferred.lower() != t.term.lower():
                # Non-banned but has preferred alternative (e.g. "Northwind" vs "Northwind Coffee" on first mention)
                # If matched text does not already match preferred
                if not content[start:].startswith(t.preferred):
                    findings.append(
                        FindingBase(
                            quoted_text=matched_text,
                            start=start,
                            end=end,
                            severity="warning",
                            reason=f"Brand term guideline: {t.notes or f'Preferred term is {t.preferred}'}".strip(),
                            source_ref=f"TERM-{t.term.upper()}",
                            source_version=1,
                            confidence="high",
                            suggestion=f"Replace with '{t.preferred}'",
                            status="open",
                        )
                    )

    # 2. Readability check (textstat)
    if len(content.strip().split()) >= 15:
        try:
            reading_ease = textstat.flesch_reading_ease(content)
            grade_level = textstat.flesch_kincaid_grade(content)
            if reading_ease < 30.0 or grade_level > 15.0:
                first_sentence = content.split(".")[0].strip() or content[:80]
                findings.append(
                    FindingBase(
                        quoted_text=first_sentence,
                        start=0,
                        end=min(len(first_sentence), len(content)),
                        severity="warning",
                        reason=f"High readability complexity detected (Flesch Reading Ease: {reading_ease:.1f}, Grade Level: {grade_level:.1f}). Content may be difficult for general audience to comprehend.",
                        source_ref="STYLE-READABILITY",
                        source_version=1,
                        confidence="high",
                        suggestion="Consider breaking into shorter, simpler sentences to enhance clarity.",
                        status="open",
                    )
                )
        except Exception:
            pass

    return findings

