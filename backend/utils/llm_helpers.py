"""Shared LLM response helpers used across all agents.

Consolidates duplicated _extract_content, _strip_code_fences, _extract_json_blob,
and provides a unified _call_openrouter with retry.
"""
from __future__ import annotations

import os
from typing import Any

from .retry import post_with_retry

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "z-ai/glm-4.5-air:free"


def extract_content(payload: dict[str, Any]) -> str:
    """Extract text content from an OpenRouter / OpenAI-style response payload."""
    if "choices" in payload and payload["choices"]:
        message = payload["choices"][0].get("message", {})
        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("text"):
                    return str(part["text"])
        if isinstance(content, str):
            return content
    return ""


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from LLM output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    return cleaned.strip()


def extract_json_blob(text: str) -> str:
    """Extract the first JSON object {...} from text."""
    cleaned = strip_code_fences(text)
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def extract_json_array(text: str) -> str:
    """Extract the first JSON array [...] from text."""
    cleaned = strip_code_fences(text)
    if cleaned.startswith("[") and cleaned.endswith("]"):
        return cleaned
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return "[]"


async def call_openrouter(
    *,
    system_prompt: str,
    user_message: str,
    api_key: str | None = None,
    model: str | None = None,
    max_tokens: int = 1500,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """Unified OpenRouter call with retry logic.

    Returns the raw parsed JSON payload (use extract_content to get text).
    """
    key = api_key or os.getenv("OPEN_ROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("Missing OPEN_ROUTER_API_KEY")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model or os.getenv("DEFAULT_MODEL", DEFAULT_MODEL),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    timeout_seconds = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "30"))
    return await post_with_retry(
        OPENROUTER_URL,
        headers=headers,
        json_body=body,
        timeout=timeout_seconds,
    )
