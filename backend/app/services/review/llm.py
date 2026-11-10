"""LLM Integration service supporting OpenAI, Google Gemini, OpenRouter, and Ollama."""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Union

from app.config import settings

logger = logging.getLogger(__name__)


def is_llm_configured() -> bool:
    """Check if a valid LLM API key is provided and mock_ai is disabled."""
    if settings.mock_ai:
        return False
    key = settings.llm_api_key.strip()
    return bool(key and key != "your-api-key-here" and len(key) > 8)


def extract_json_from_response(text: str) -> Union[Dict[str, Any], List[Any], None]:
    """Extract JSON object or array from LLM response text."""
    text = text.strip()
    # Match ```json ... ``` blocks
    json_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if json_block:
        candidate = json_block.group(1).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to find first [ or {
    first_bracket = min(
        [pos for pos in [text.find("{"), text.find("[")] if pos != -1] or [-1]
    )
    last_bracket = max([text.rfind("}"), text.rfind("]")])
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        try:
            return json.loads(text[first_bracket : last_bracket + 1])
        except Exception:
            pass

    return None


def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> Optional[str]:
    """Invoke the configured LLM using OpenAI-compatible SDK."""
    if not is_llm_configured():
        return None

    try:
        from openai import OpenAI

        client_kwargs: Dict[str, Any] = {
            "api_key": settings.llm_api_key,
        }
        if settings.llm_base_url:
            client_kwargs["base_url"] = settings.llm_base_url

        client = OpenAI(**client_kwargs)

        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.warning("LLM API call failed, falling back to heuristics: %s", exc)
        return None


def call_llm_json(system_prompt: str, user_prompt: str) -> Union[Dict[str, Any], List[Any], None]:
    """Invoke the LLM and return parsed JSON."""
    raw = call_llm(
        system_prompt=system_prompt + "\nYou must respond strictly with valid JSON. Do not include extra conversational text.",
        user_prompt=user_prompt,
    )
    if not raw:
        return None
    return extract_json_from_response(raw)

