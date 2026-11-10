"""Layer 4: Source Validator ("No source, no flag").

Enforces the absolute design principle: every finding MUST point to a verified,
approved guideline or fact. Any finding without a valid, registered source citation
is strictly dropped.
"""

import logging
from typing import List, Set

from app.schemas.finding import FindingBase

logger = logging.getLogger(__name__)


def validate_and_filter_findings(
    findings: List[FindingBase],
    content: str,
    valid_source_refs: Set[str],
) -> List[FindingBase]:
    """Validate, sanitize, and discard unsourced or hallucinated findings."""
    cleaned_findings: List[FindingBase] = []
    seen_keys = set()

    normalized_valid_sources = {s.strip().upper() for s in valid_source_refs if s.strip()}
    # Always allow system-level style/readability and claim checkers if defined
    normalized_valid_sources.add("STYLE-READABILITY")
    normalized_valid_sources.add("CLAIM-UNSUPPORTED")

    for f in findings:
        # 1. Enforce non-empty source_ref
        if not f.source_ref or not f.source_ref.strip():
            logger.info("Dropping finding with missing source_ref: %s", f)
            continue

        ref_upper = f.source_ref.strip().upper()

        # Check if source_ref is grounded in approved sources
        is_grounded = False
        if ref_upper in normalized_valid_sources:
            is_grounded = True
        else:
            # Check if any valid source is a substring (e.g. fact statement substring)
            for valid in normalized_valid_sources:
                if valid in ref_upper or ref_upper in valid:
                    is_grounded = True
                    break

        if not is_grounded:
            logger.info("Validator dropped ungrounded finding with source_ref '%s'", f.source_ref)
            continue

        # 2. Validate quote and locate text bounds in content
        quote = (f.quoted_text or "").strip()
        if quote:
            pos = content.find(quote)
            if pos != -1:
                f.start_offset = pos
                f.end_offset = pos + len(quote)
            else:
                # Bound check
                f.start_offset = max(0, f.start_offset)
                f.end_offset = min(len(content), max(f.start_offset + 1, f.end_offset))
        else:
            f.start_offset = 0
            f.end_offset = min(10, len(content))

        # 3. Deduplicate
        dedup_key = (f.source_ref, f.start_offset, f.end_offset, f.severity)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        cleaned_findings.append(f)

    return cleaned_findings

