"""Layer 3: Grounded AI Tone and Brand Guideline Evaluation."""

import re
from typing import List, Optional

from app.models.source import GuidelineRule
from app.schemas.finding import FindingBase
from app.services.review.llm import call_llm_json, is_llm_configured


def evaluate_tone_with_llm(content: str, rules: List[GuidelineRule]) -> Optional[List[FindingBase]]:
    """Evaluate content tone and brand policies using the configured LLM."""
    if not is_llm_configured() or not rules:
        return None

    rules_prompt = []
    for r in rules:
        rules_prompt.append(f"- Rule ID: {r.rule_id} | Category: {r.category or 'General'}\n  Text: {r.text}")

    system_prompt = (
        "You are ProofLine's Grounded Brand Governance AI. You strictly audit content against authorized brand guidelines.\n\n"
        "Active Brand Guidelines:\n" + "\n\n".join(rules_prompt) + "\n\n"
        "CRITICAL INSTRUCTIONS (\"No source, no flag\"):\n"
        "1. Every single finding MUST explicitly violate one of the active Brand Guidelines listed above.\n"
        "2. The 'source_ref' field MUST be the exact Rule ID of the violated guideline (e.g. 'TONE-01'). Never leave it blank.\n"
        "3. Provide minimal, respectful, constructive 'suggestion' rewrites that preserve the creator's intended message.\n\n"
        "Return a JSON array of findings with this exact schema:\n"
        "[\n"
        "  {\n"
        "    \"quoted_text\": \"exact text snippet\",\n"
        "    \"severity\": \"blocker\" | \"warning\" | \"note\",\n"
        "    \"reason\": \"plain-language explanation of why this violates the specific guideline\",\n"
        "    \"source_ref\": \"RULE_ID_HERE\",\n"
        "    \"confidence\": \"high\" | \"medium\" | \"low\",\n"
        "    \"suggestion\": \"context-aware fix\"\n"
        "  }\n"
        "]\n"
    )

    user_prompt = f"Audit this draft against the guidelines:\n\n{content}"

    result = call_llm_json(system_prompt, user_prompt)
    if not isinstance(result, list):
        return None

    findings: List[FindingBase] = []
    rule_versions = {r.rule_id: r.version for r in rules}

    for item in result:
        if not isinstance(item, dict):
            continue

        raw_quote = str(item.get("quoted_text", "")).strip()
        source_ref = str(item.get("source_ref", "")).strip()
        if not raw_quote or not source_ref or source_ref not in rule_versions:
            # Respect "No source, no flag"
            continue

        start_idx = content.find(raw_quote)
        end_idx = start_idx + len(raw_quote) if start_idx != -1 else 0
        if start_idx == -1:
            start_idx = 0
            end_idx = min(len(raw_quote), len(content))

        severity = str(item.get("severity", "warning")).lower()
        if severity not in ["blocker", "warning", "note"]:
            severity = "warning"

        confidence = str(item.get("confidence", "high")).lower()
        if confidence not in ["high", "medium", "low"]:
            confidence = "high"

        findings.append(
            FindingBase(
                quoted_text=raw_quote,
                start=start_idx,
                end=end_idx,
                severity=severity,
                reason=item.get("reason", "Guideline deviation detected."),
                source_ref=source_ref,
                source_version=rule_versions.get(source_ref, 1),
                confidence=confidence,
                suggestion=item.get("suggestion"),
                status="open",
            )
        )

    return findings


def evaluate_tone_heuristics(content: str, rules: List[GuidelineRule]) -> List[FindingBase]:
    """Heuristic brand tone evaluator when LLM is unavailable."""
    findings: List[FindingBase] = []

    for rule in rules:
        rule_id = rule.rule_id
        text_lower = rule.text.lower()

        # TONE-01: Health claims / absolute statements
        if "health" in text_lower or "cure" in text_lower or "TONE-01" in rule_id:
            health_patterns = [
                r"\b(?:healthiest|cures|cure for|prevents disease|medicinal miracle|proven to heal|detoxify your body)\b",
                r"\b(?:eliminates stress completely|guaranteed wellness|anti-aging wonder)\b",
            ]
            for pat in health_patterns:
                for match in re.finditer(pat, content, flags=re.IGNORECASE):
                    quote = match.group(0)
                    findings.append(
                        FindingBase(
                            quoted_text=quote,
                            start=match.start(),
                            end=match.end(),
                            severity="blocker",
                            reason=f"Absolute health claim violates {rule_id}. Use hedged language like 'crafted with wellness in mind'.",
                            source_ref=rule_id,
                            source_version=rule.version,
                            confidence="high",
                            suggestion="Replace with hedged language (e.g. 'may support natural wellness')",
                            status="open",
                        )
                    )

        # TONE-02: Aggressive sales / pressure tactics / brand voice
        if "aggressive" in text_lower or "sales" in text_lower or "voice" in text_lower or "TONE-02" in rule_id:
            sales_patterns = [
                r"\b(?:ACT NOW(?:\s+BEFORE[^.!?]*)?|BUY NOW(?:\s+OR[^.!?]*)?|LIMITED TIME ONLY|HURRY(?:\s+BEFORE[^.!?]*)?|DON'T WAIT|SUPPLIES RUN OUT)\b",
                r"\b(?:pressure tactics|unbeatable prices you can't refuse|run don't walk|while supplies last)\b",
            ]
            for pat in sales_patterns:
                for match in re.finditer(pat, content, flags=re.IGNORECASE):
                    quote = match.group(0)
                    findings.append(
                        FindingBase(
                            quoted_text=quote,
                            start=match.start(),
                            end=match.end(),
                            severity="warning",
                            reason=f"Aggressive pressure language breaches {rule_id} brand tone standard.",
                            source_ref=rule_id,
                            source_version=rule.version,
                            confidence="high",
                            suggestion="Adopt a warm, inviting tone (e.g. 'Explore our seasonal roast at your convenience').",
                            status="open",
                        )
                    )

    return findings


def evaluate_grounded_tone(content: str, rules: List[GuidelineRule]) -> List[FindingBase]:
    """Execute Layer 3 Grounded Tone & Guideline review."""
    llm_findings = evaluate_tone_with_llm(content, rules)
    if llm_findings is not None:
        return llm_findings
    return evaluate_tone_heuristics(content, rules)
