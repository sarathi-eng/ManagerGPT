from __future__ import annotations

import json
import os

import httpx
from ..utils.parse_llm_json import parse_llm_json

SYSTEM_PROMPT = """
You are a business classification AI.

Your job is to understand the user's business scenario BEFORE analysis.

Identify:
- business_type: startup | expansion | conversion | pricing | diagnosis
- industry: specific real-world industry
- target_customer
- real_competitors (actual competitors, not big tech unless relevant)
- cost_structure: low | medium | high
- geography_impact: low | medium | high importance

Return ONLY valid JSON.
"""


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "z-ai/glm-4.5-air:free"


async def classify_business(goal: str) -> dict:
    api_key = os.getenv("OPEN_ROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPEN_ROUTER_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": goal},
        ],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(OPENROUTER_URL, headers=headers, json=body)
        resp.raise_for_status()
        payload = resp.json()

    content = ""
    if "choices" in payload and payload["choices"]:
        content = payload["choices"][0].get("message", {}).get("content", "")

    return parse_llm_json(content)
