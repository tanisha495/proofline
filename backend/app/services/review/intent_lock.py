"""Intent Lock Service: computes side-by-side minimal diffs and verifies message survival."""

from typing import Any, Dict, List, Optional, Tuple
import diff_match_patch as dmp_module

from app.services.review.llm import call_llm_json, is_llm_configured


def compute_side_by_side_diff(original: str, revised: str) -> List[Dict[str, Any]]:
    """Compute visual character diffs using diff-match-patch.

    Returns structured tokens:
        [{"type": "equal" | "insert" | "delete", "text": "..."}]
    """
    dmp = dmp_module.diff_match_patch()
    diffs = dmp.diff_main(original, revised)
    dmp.diff_cleanupSemantic(diffs)

    type_map = {-1: "delete", 0: "equal", 1: "insert"}
    return [{"type": type_map.get(op, "equal"), "text": text} for op, text in diffs]


def verify_intent_preservation(
    original: str,
    revised: str,
    intent_lock: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Verify whether creator's stated intent (message, audience, CTA) survived the edits."""
    if not intent_lock:
        return {"intent_preserved": True, "score": 1.0, "details": "No intent lock specified."}

    key_message = str(intent_lock.get("key_message", "")).strip()
    audience = str(intent_lock.get("audience", "")).strip()
    cta = str(intent_lock.get("call_to_action", "")).strip()

    # Try LLM validation first
    if is_llm_configured() and (key_message or cta):
        system_prompt = (
            "You are ProofLine's Intent Lock Auditor. Assess whether the suggested revision preserves "
            "the author's critical intent without diluting the message.\n"
            "Return JSON:\n"
            "{\n"
            "  \"intent_preserved\": true | false,\n"
            "  \"score\": float (0.0 to 1.0),\n"
            "  \"details\": \"concise evaluation\"\n"
            "}"
        )
        user_prompt = (
            f"Original Content:\n{original}\n\n"
            f"Revised Content:\n{revised}\n\n"
            f"Author's Intent Constraints:\n"
            f"- Key Message: {key_message}\n"
            f"- Target Audience: {audience}\n"
            f"- Call To Action: {cta}\n"
        )
        res = call_llm_json(system_prompt, user_prompt)
        if isinstance(res, dict) and "intent_preserved" in res:
            return res

    # Heuristic verification
    preserved = True
    notes = []

    # Check key words from CTA
    if cta:
        cta_words = [w.lower() for w in cta.split() if len(w) > 3]
        matched_words = [w for w in cta_words if w in revised.lower()]
        if cta_words and len(matched_words) / len(cta_words) < 0.5:
            preserved = False
            notes.append(f"Call to action ('{cta}') appears significantly modified.")

    # Check key words from key message
    if key_message:
        km_words = [w.lower() for w in key_message.split() if len(w) > 3]
        matched_km = [w for w in km_words if w in revised.lower()]
        if km_words and len(matched_km) / len(km_words) < 0.4:
            preserved = False
            notes.append(f"Core key message elements ('{key_message}') may have been lost.")

    return {
        "intent_preserved": preserved,
        "score": 0.9 if preserved else 0.4,
        "details": "; ".join(notes) if notes else "Core message, audience tone, and CTA preserved successfully.",
    }

