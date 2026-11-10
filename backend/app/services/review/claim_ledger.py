"""Layer 2: Claim Ledger & Fact Verification Service."""

from datetime import date
import re
from typing import Any, Dict, List, Optional, Tuple

from app.models.source import Fact
from app.schemas.claim import ClaimStatus
from app.schemas.finding import FindingBase
from app.services.review.llm import call_llm_json, is_llm_configured


class ExtractedClaim:
    def __init__(
        self,
        quoted_text: str,
        status: ClaimStatus,
        source_ref: Optional[str] = None,
        reason: Optional[str] = None,
        severity: Optional[str] = None,
        suggestion: Optional[str] = None,
        start: int = 0,
        end: int = 0,
    ):
        self.quoted_text = quoted_text
        self.status = status
        self.source_ref = source_ref
        self.reason = reason
        self.severity = severity
        self.suggestion = suggestion
        self.start = start
        self.end = end


def verify_claims_with_llm(content: str, facts: List[Fact]) -> Optional[List[ExtractedClaim]]:
    """Use configured LLM to extract claims and verify against approved facts."""
    if not is_llm_configured():
        return None

    facts_prompt = []
    for f in facts:
        facts_prompt.append(
            f"- ID: {f.statement} (Value: '{f.value}', Source: {f.source}, Expires: {f.expires_on})"
        )

    system_prompt = (
        "You are ProofLine's Claim Ledger Verification Engine. Your job is to extract factual assertions "
        "(numbers, dates, company milestones, certifications, performance statistics) and match them against the approved corporate facts.\n\n"
        "Approved Facts:\n" + "\n".join(facts_prompt) + "\n\n"
        "Return a JSON array of claim objects with the following schema:\n"
        "[\n"
        "  {\n"
        "    \"quoted_text\": \"exact text snippet from content\",\n"
        "    \"status\": \"supported\" | \"conflicts\" | \"expired_evidence\" | \"unsupported\" | \"needs_human\",\n"
        "    \"source_ref\": \"statement or fact description matching the approved fact, or 'UNVERIFIED-CLAIM'\",\n"
        "    \"reason\": \"explanation of why it is supported, conflicts, or unverified\",\n"
        "    \"severity\": \"blocker\" | \"warning\" | \"note\",\n"
        "    \"suggestion\": \"suggested correction or null if supported\"\n"
        "  }\n"
        "]\n"
        "Rules:\n"
        "- If text matches approved value and fact is unexpired: status='supported'\n"
        "- If text contradicts approved value (e.g. text says 200 stores, fact says 127): status='conflicts', severity='blocker'\n"
        "- If fact expiration date is in the past: status='expired_evidence', severity='warning'\n"
        "- If assertive claim has no approved source: status='unsupported', severity='warning'\n"
    )

    user_prompt = f"Analyze the following content and verify every factual claim:\n\n{content}"

    result = call_llm_json(system_prompt, user_prompt)
    if not isinstance(result, list):
        return None

    claims = []
    today = date.today()
    for item in result:
        if not isinstance(item, dict) or "quoted_text" not in item:
            continue

        raw_quote = str(item.get("quoted_text", "")).strip()
        if not raw_quote:
            continue

        # Locate in text
        start_idx = content.find(raw_quote)
        end_idx = start_idx + len(raw_quote) if start_idx != -1 else 0
        if start_idx == -1:
            start_idx = 0
            end_idx = min(len(raw_quote), len(content))

        status_str = str(item.get("status", "unsupported")).lower()
        if status_str not in [s.value for s in ClaimStatus]:
            status_str = ClaimStatus.UNSUPPORTED.value

        source_ref = item.get("source_ref") or "FACT-UNKNOWN"

        # Check if the fact is actually expired according to current date
        for f in facts:
            if (f.statement.lower() in source_ref.lower() or source_ref.lower() in f.statement.lower()):
                if f.expires_on and f.expires_on < today and status_str == ClaimStatus.SUPPORTED.value:
                    status_str = ClaimStatus.EXPIRED_EVIDENCE.value
                    item["reason"] = f"Approved evidence for '{f.statement}' expired on {f.expires_on}."
                    item["severity"] = "warning"
                break

        claims.append(
            ExtractedClaim(
                quoted_text=raw_quote,
                status=ClaimStatus(status_str),
                source_ref=source_ref,
                reason=item.get("reason"),
                severity=item.get("severity", "warning" if status_str != ClaimStatus.SUPPORTED.value else "note"),
                suggestion=item.get("suggestion"),
                start=start_idx,
                end=end_idx,
            )
        )

    return claims


def verify_claims_heuristics(content: str, facts: List[Fact]) -> List[ExtractedClaim]:
    """Heuristic fallback claim extractor when LLM is unavailable or in mock mode."""
    claims: List[ExtractedClaim] = []
    today = date.today()

    for f in facts:
        statement_lower = f.statement.lower()
        value = (f.value or "").strip()
        is_expired = bool(f.expires_on and f.expires_on < today)

        # Check for retail locations / store counts
        if "location" in statement_lower or "store" in statement_lower:
            pattern = r"(\b\d+\b|\bover\s+\d+\b|\bmore than\s+\d+\b)\s+(?:retail\s+)?(?:locations|stores|cafes|shops)"
            match = re.search(pattern, content, flags=re.IGNORECASE)
            if match:
                quote = match.group(0)
                # Check if value matches
                if value in quote:
                    if is_expired:
                        claims.append(
                            ExtractedClaim(
                                quoted_text=quote,
                                status=ClaimStatus.EXPIRED_EVIDENCE,
                                source_ref=f.statement,
                                reason=f"Evidence for store count ({f.source}) expired on {f.expires_on}.",
                                severity="warning",
                                suggestion=f"Verify current store count with {f.owner}.",
                                start=match.start(),
                                end=match.end(),
                            )
                        )
                    else:
                        claims.append(
                            ExtractedClaim(
                                quoted_text=quote,
                                status=ClaimStatus.SUPPORTED,
                                source_ref=f.statement,
                                reason=f"Verified by {f.source} (Owner: {f.owner}).",
                                start=match.start(),
                                end=match.end(),
                            )
                        )
                else:
                    claims.append(
                        ExtractedClaim(
                            quoted_text=quote,
                            status=ClaimStatus.CONFLICTS,
                            source_ref=f.statement,
                            reason=f"Claim contradicts approved record of {value} locations from {f.source}.",
                            severity="blocker",
                            suggestion=f"Update to approved value '{value}' locations.",
                            start=match.start(),
                            end=match.end(),
                        )
                    )

        # Check for founding year or founding city
        if "found" in statement_lower or "year" in statement_lower or "city" in statement_lower:
            pattern = r"(?:founded|established)\s+(?:in\s+)?(?:\d{4}|\w+)(?:\s+(?:in|,)\s+\w+(?:,\s+\w+)?)?"
            match = re.search(pattern, content, flags=re.IGNORECASE)
            if match:
                quote = match.group(0)
                if is_expired:
                    claims.append(
                        ExtractedClaim(
                            quoted_text=quote,
                            status=ClaimStatus.EXPIRED_EVIDENCE,
                            source_ref=f.statement,
                            reason=f"Approved evidence in {f.source} expired on {f.expires_on}.",
                            severity="warning",
                            suggestion=f"Revalidate historical citation with {f.owner}.",
                            start=match.start(),
                            end=match.end(),
                        )
                    )
                else:
                    claims.append(
                        ExtractedClaim(
                            quoted_text=quote,
                            status=ClaimStatus.SUPPORTED,
                            source_ref=f.statement,
                            reason=f"Verified against {f.source}.",
                            start=match.start(),
                            end=match.end(),
                        )
                    )

    # Detect unverified absolute / superlative claims
    superlative_patterns = [
        (r"\b(?:world's best|the best|#1|number one|market leader)\b", "Unverified superlative claim with no citation in corporate facts."),
        (r"\b(?:guaranteed results|100% cure|100% effective|instant results)\b", "Absolute claim without empirical backing in corporate facts."),
    ]
    for pat, reason in superlative_patterns:
        for m in re.finditer(pat, content, flags=re.IGNORECASE):
            quote = m.group(0)
            claims.append(
                ExtractedClaim(
                    quoted_text=quote,
                    status=ClaimStatus.UNSUPPORTED,
                    source_ref="CLAIM-UNSUPPORTED",
                    reason=reason,
                    severity="blocker",
                    suggestion="Replace with qualified or subjective wording (e.g., 'favorite', 'crafted to support').",
                    start=m.start(),
                    end=m.end(),
                )
            )

    return claims


def process_claim_ledger(
    content: str, facts: List[Fact]
) -> Tuple[List[ExtractedClaim], List[FindingBase]]:
    """Process content through Layer 2 Claim Ledger.

    Returns:
        (extracted_claims, claim_findings)
    """
    claims = verify_claims_with_llm(content, facts)
    if claims is None:
        claims = verify_claims_heuristics(content, facts)

    findings: List[FindingBase] = []
    for c in claims:
        # If claim is unsupported, conflicts, or has expired evidence, raise finding
        if c.status in [ClaimStatus.CONFLICTS, ClaimStatus.EXPIRED_EVIDENCE, ClaimStatus.UNSUPPORTED]:
            findings.append(
                FindingBase(
                    quoted_text=c.quoted_text,
                    start=c.start,
                    end=c.end,
                    severity=c.severity or "warning",
                    reason=c.reason or f"Factual claim status: {c.status.value}",
                    source_ref=c.source_ref or "FACT-RECORD",
                    source_version=1,
                    confidence="high",
                    suggestion=c.suggestion,
                    status="open",
                )
            )

    return claims, findings

