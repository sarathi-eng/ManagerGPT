from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .. import database
from ..utils.parse_llm_json import parse_llm_json

SYSTEM_PROMPT = """
You are a Fact-Checking AI. Identify weak or unsupported claims.

Flag claims if:
- No source provided
- Source is unreliable (forum, reddit, quora without corroboration)
- Claim is too specific without citation
- Numbers lack source
- "Estimated" or "approximately" without basis

Output ONLY valid JSON array:
[
  {
    "claim": "Market will grow 47% next year",
    "issue": "Overly specific prediction without source",
    "severity": "HIGH"
  }
]
"""

MODEL = os.getenv("HALLUCINATION_MODEL", "z-ai/glm-4.5-air:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 800
TEMPERATURE = 0.2


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


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    return cleaned.strip()


def _extract_json_blob(text: str) -> str:
    cleaned = _strip_code_fences(text)
    if cleaned.startswith("[") and cleaned.endswith("]"):
        return cleaned
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return "[]"


async def _call_openrouter(prompt: str, api_key: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
    }
    timeout_seconds = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "20"))
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(OPENROUTER_URL, headers=headers, json=body)
        response.raise_for_status()
        return response.json()


async def detect_hallucinations(text: str, sources: list[str], session_id: int) -> list[dict]:
    api_key = os.getenv("OPEN_ROUTER_API_KEY")
    if not api_key or not text:
        return []

    prompt = f"Text: {text}\nSources: {sources}"
    try:
        payload = await _call_openrouter(prompt, api_key)
        content = _extract_content(payload)
        data = parse_llm_json(_extract_json_blob(content), expect_array=True)
        if not isinstance(data, list):
            return []
    except Exception as exc:  # noqa: BLE001
        database.log_agent_activity(
            session_id,
            "Hallucination Detector",
            f"Detector failed: {exc}",
            "rejected",
            None,
        )
        return []

    normalized: list[dict] = []
    for item in data:
        claim = str(item.get("claim", "")).strip()
        issue = str(item.get("issue", "")).strip()
        severity = str(item.get("severity", "MEDIUM")).upper()
        if not claim or not issue:
            continue
        if severity not in {"LOW", "MEDIUM", "HIGH"}:
            severity = "MEDIUM"
        normalized.append({"claim": claim, "issue": issue, "severity": severity})

    return normalized