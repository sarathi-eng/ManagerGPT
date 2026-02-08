from __future__ import annotations

import os
from typing import Any

import httpx

from .. import database

SYSTEM_PROMPT = """
You are a Senior Executive Advisor. Distill complex analysis into ONE compelling paragraph.

Your narrative must:
1. Start with clear verdict (viable/not viable/conditional)
2. State the key constraint/driver
3. Give specific condition for success
4. End with actionable implication

BAD NARRATIVE:
"This business has potential but requires validation in several areas..."
→ Vague, no clarity

GOOD NARRATIVE:
"This business is VIABLE in dense campus environments but fails in low-population areas. The critical threshold: 500+ students per location to achieve unit economics (₹28 cost vs ₹50 revenue per order). Below this density, delivery costs kill margins. Recommendation: Start with ONE high-density campus cluster, prove 8%+ weekly adoption within 30 days, then replicate. Avoid broad launches."
→ Clear verdict, specific numbers, actionable

Write as if briefing a CEO who has 30 seconds.

Output ONLY the paragraph text, no JSON.
"""

MODEL = os.getenv("EXECUTIVE_NARRATIVE_MODEL", "z-ai/glm-4.5-air:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 700
TEMPERATURE = 0.7


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


def _fallback_narrative(business_analysis: dict, business_strategy: dict) -> str:
    recommendation = str(business_analysis.get("recommendation", "INVESTIGATE")).upper()
    breakeven = business_strategy.get("breakeven", {}) if isinstance(business_strategy, dict) else {}
    adoption = business_strategy.get("adoption_threshold", {}) if isinstance(business_strategy, dict) else {}
    months_min = breakeven.get("months_min", "?")
    months_max = breakeven.get("months_max", "?")
    key_driver = breakeven.get("key_driver") or "unit economics"
    adoption_pct = adoption.get("minimum_adoption_pct", "?")
    if recommendation == "PROCEED":
        verdict = "VIABLE"
    elif recommendation == "STOP":
        verdict = "NOT VIABLE"
    else:
        verdict = "CONDITIONAL"
    return (
        f"This business is {verdict}. The key driver is {key_driver}, with break-even expected in "
        f"{months_min}-{months_max} months if adoption reaches {adoption_pct}%. "
        "Recommendation: pilot a focused launch, validate adoption and margins quickly, then scale."
    )


async def _call_openrouter(system_prompt: str, user_message: str, api_key: str, temperature: float) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": temperature,
    }
    timeout_seconds = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "20"))
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(OPENROUTER_URL, headers=headers, json=body)
        response.raise_for_status()
        return response.json()


async def generate_decision_narrative(
    business_analysis: dict,
    business_strategy: dict,
    session_id: int,
) -> str:
    """
    Create compelling one-paragraph decision summary.
    """

    system_prompt = SYSTEM_PROMPT

    breakeven = business_strategy.get("breakeven", {}) if isinstance(business_strategy, dict) else {}
    adoption = business_strategy.get("adoption_threshold", {}) if isinstance(business_strategy, dict) else {}
    unit_economics = (
        business_strategy.get("unit_economics", {}) if isinstance(business_strategy, dict) else {}
    )
    business_classification = business_analysis.get("business_classification", {}) or {}

    user_message = f"""
Generate executive narrative from this analysis:

Recommendation: {business_analysis.get('recommendation', 'INVESTIGATE')}
Confidence: {float(business_analysis.get('confidence', 0)):.0%}

Key Finding: {str(business_analysis.get('reasoning', ''))[:300]}

Business Type: {business_classification.get('business_type', 'Unknown')}
Target: {business_classification.get('target_customer', 'Unknown')}

Break-even: {breakeven.get('months_min', '?')}-{breakeven.get('months_max', '?')} months
Key Driver: {breakeven.get('key_driver', 'Unit economics')}

Unit Economics: ₹{unit_economics.get('cost_per_unit', '?')} cost, ₹{unit_economics.get('revenue_per_unit', '?')} revenue

Critical Threshold: {adoption.get('minimum_adoption_pct', '?')}% adoption needed

Write the 1-paragraph executive narrative.
"""

    database.log_agent_activity(
        session_id,
        "Executive Summary",
        "Generating decision narrative...",
        "working",
        None,
    )

    api_key = os.getenv("OPEN_ROUTER_API_KEY")
    if not api_key:
        database.log_agent_activity(
            session_id,
            "Executive Summary",
            "Narrative generator unavailable; using default summary.",
            "warning",
            None,
        )
        return _fallback_narrative(business_analysis, business_strategy)

    try:
        response = await _call_openrouter(system_prompt, user_message, api_key, TEMPERATURE)
        narrative = _extract_content(response).strip()

        if len(narrative) < 150 or len(narrative) > 600:
            response = await _call_openrouter(
                system_prompt,
                user_message + "\n\nMake it 200-400 words.",
                api_key,
                0.8,
            )
            narrative = _extract_content(response).strip()

        if not narrative:
            raise ValueError("Empty narrative")

        database.log_agent_activity(
            session_id,
            "Executive Summary",
            "Narrative complete",
            "complete",
            None,
        )
        return narrative
    except Exception:  # noqa: BLE001
        database.log_agent_activity(
            session_id,
            "Executive Summary",
            "Narrative generation failed; using default summary.",
            "warning",
            None,
        )
        return _fallback_narrative(business_analysis, business_strategy)
