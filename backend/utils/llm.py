from __future__ import annotations

import os
from typing import Any, Optional

from .retry import post_with_retry

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "z-ai/glm-4.5-air:free"


def _extract_content(payload: dict[str, Any]) -> str:
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


async def call_llm(
    prompt: str,
    temperature: float = 0.2,
    model: Optional[str] = None,
) -> str:
    api_key = os.getenv("OPEN_ROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPEN_ROUTER_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model or os.getenv("MECHANISM_MODEL", DEFAULT_MODEL),
        "messages": [
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 700,
        "temperature": temperature,
    }
    timeout_seconds = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "20"))
    payload = await post_with_retry(
        OPENROUTER_URL,
        headers=headers,
        json_body=body,
        timeout=timeout_seconds,
    )
    return _extract_content(payload)
