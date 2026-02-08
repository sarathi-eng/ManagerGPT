from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from .. import database
from ..utils.json_parser import clean_json_response
from ..utils.parse_llm_json import parse_llm_json

SYSTEM_PROMPT = """
You are a Strategic Reasoning AI. Your job is to defend a decision by explaining why ALTERNATIVE decisions were rejected.

For a given recommendation (PROCEED/STOP/INVESTIGATE), explain:

1. Why NOT the opposite extreme?
2. Why NOT the middle ground?

Be SPECIFIC and DATA-DRIVEN. Reference actual numbers from the analysis.

BAD DEFENSE (Too vague):
"Why not STOP? Because there's potential."
→ Generic, no evidence

GOOD DEFENSE (Specific reasoning):
"Why not STOP? Customer demand is 68% weekly (Statista) vs competition satisfaction at 45% (TechCrunch) - a 23-point opportunity gap. Market growing 12% CAGR. The problem isn't demand, it's execution risk."
→ Specific numbers, clear logic

BAD DEFENSE (Too vague):
"Why not PROCEED confidently? There are risks."
→ No specifics

GOOD DEFENSE (Specific reasoning):
"Why not PROCEED confidently? Unit economics show only ₹22 margin per order (₹50 revenue - ₹28 cost). At current CAC of ₹180, payback requires 8+ orders per customer. Industry churn at 35%/month means most users lost before payback. Need proof of retention first."
→ Math shown, specific concern identified

Output ONLY valid JSON:
{
  "why_not_stop": "Specific data-driven reason with numbers",
  "why_not_investigate": "Specific data-driven reason with numbers",
  "why_not_proceed": "Specific data-driven reason with numbers"
}

Include the defenses for the 2 decisions NOT chosen.
"""

MODEL = os.getenv("DECISION_DEFENDER_MODEL", "z-ai/glm-4.5-air:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 800
TEMPERATURE = 0.3


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


async def _call_openrouter(system_prompt: str, user_message: str, api_key: str) -> dict[str, Any]:
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
        "temperature": TEMPERATURE,
    }
    timeout_seconds = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "20"))
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(OPENROUTER_URL, headers=headers, json=body)
        response.raise_for_status()
        return response.json()


async def generate_decision_defense(
    recommendation: str,
    business_analysis: dict,
    business_strategy: dict,
    research_results: list[dict],
    session_id: int,
) -> dict:
    """
    Generate counterargument defenses for the decision.

    Explains why we DIDN'T choose the other options.
    """

    defenses_needed = {
        "PROCEED": ["why_not_stop", "why_not_investigate"],
        "STOP": ["why_not_proceed", "why_not_investigate"],
        "INVESTIGATE": ["why_not_proceed", "why_not_stop"],
    }

    needed = defenses_needed.get(recommendation, [])
    key_data = extract_defense_ammunition(business_analysis, business_strategy, research_results)

    unit_economics = business_strategy.get("unit_economics", {}) if isinstance(business_strategy, dict) else {}
    breakeven = business_strategy.get("breakeven", {}) if isinstance(business_strategy, dict) else {}
    adoption = (
        business_strategy.get("adoption_threshold", {}) if isinstance(business_strategy, dict) else {}
    )
    classification = business_analysis.get("business_classification", {}) or {}

    user_message = f"""
DECISION MADE: {recommendation}

ANALYSIS SUMMARY:
- Confidence: {float(business_analysis.get('confidence', 0)):.0%}
- Reasoning: {str(business_analysis.get('reasoning', ''))[:400]}

KEY DATA POINTS:
{key_data}

UNIT ECONOMICS:
- Cost per unit: ₹{unit_economics.get('cost_per_unit', '?')}
- Revenue per unit: ₹{unit_economics.get('revenue_per_unit', '?')}
- Margin: {float(unit_economics.get('gross_margin_pct', 0)):.0f}%
- Health: {unit_economics.get('health', 'UNKNOWN')}

MARKET METRICS:
- Target segment: {classification.get('target_customer', 'Unknown')}
- Break-even timeline: {breakeven.get('months_min', '?')}-{breakeven.get('months_max', '?')} months
- Required adoption: {adoption.get('minimum_adoption_pct', '?')}%

TOP PROS:
{format_list((business_analysis.get('pros') or [])[:3])}

TOP CONS:
{format_list((business_analysis.get('cons') or [])[:3])}

Now explain why you DIDN'T choose: {', '.join(needed)}

Use specific numbers and data points from above. Be concise but precise.
"""

    database.log_agent_activity(
        session_id,
        "Decision Defense",
        "Generating counterargument defenses...",
        "working",
        None,
    )

    api_key = os.getenv("OPEN_ROUTER_API_KEY")
    if not api_key:
        database.log_agent_activity(
            session_id,
            "Decision Defense",
            "Decision defense unavailable; using fallback reasoning.",
            "warning",
            None,
        )
        return generate_fallback_defenses(recommendation, business_analysis, business_strategy)

    try:
        response = await _call_openrouter(SYSTEM_PROMPT, user_message, api_key)
        defense_text = _extract_content(response)
        defenses = parse_llm_json(clean_json_response(defense_text))

        for key in needed:
            if key in defenses:
                defense = str(defenses[key])
                has_data = bool(re.search(r"\d+%|\$[\d,]+|₹[\d,]+|\d+x", defense))
                if not has_data:
                    database.log_agent_activity(
                        session_id,
                        "Decision Defense",
                        f"⚠️ Defense for '{key}' lacks specific data - review needed",
                        "warning",
                        None,
                    )
                    defenses[key] = defense + " [Requires validation with specific metrics]"

        database.log_agent_activity(
            session_id,
            "Decision Defense",
            f"Generated {len(needed)} counterargument defenses",
            "complete",
            None,
        )

        return defenses
    except Exception:  # noqa: BLE001
        database.log_agent_activity(
            session_id,
            "Decision Defense",
            "Decision defense generation failed; using fallback reasoning.",
            "warning",
            None,
        )
        return generate_fallback_defenses(recommendation, business_analysis, business_strategy)


def extract_defense_ammunition(analysis: dict, strategy: dict, research: list[dict]) -> str:
    """Extract key numbers and facts to use in defenses"""

    ammunition = []

    for idx, res in enumerate(research, 1):
        findings = str(res.get("findings", ""))
        numbers = re.findall(r"\d+%|\$[\d,\.]+[MBK]?|₹[\d,\.]+", findings)
        if numbers:
            sentences = [s.strip() for s in findings.split(".") if s.strip()]
            data_sentences = [s for s in sentences if any(n in s for n in numbers)]
            if data_sentences:
                ammunition.append(f"Research {idx}: {data_sentences[0]}")

    breakeven = strategy.get("breakeven", {}) if isinstance(strategy, dict) else {}
    unit_economics = strategy.get("unit_economics", {}) if isinstance(strategy, dict) else {}

    if breakeven:
        ammunition.append(
            f"Break-even: {breakeven.get('months_min', '?')}-{breakeven.get('months_max', '?')} months"
        )
    if unit_economics:
        ammunition.append(
            "Margin: {:.0f}% (₹{} revenue - ₹{} cost)".format(
                float(unit_economics.get("gross_margin_pct", 0)),
                unit_economics.get("revenue_per_unit", "?"),
                unit_economics.get("cost_per_unit", "?"),
            )
        )

    customer_segments = strategy.get("customer_segments", {}) if isinstance(strategy, dict) else {}
    primary = customer_segments.get("primary", {}) if isinstance(customer_segments, dict) else {}
    if primary:
        segment = primary.get("segment")
        size = primary.get("size")
        if segment or size:
            ammunition.append(f"Primary segment: {segment} ({size})")

    return "\n".join(ammunition)


def format_list(items: list) -> str:
    """Format list for prompt"""
    if not items:
        return "- None"
    return "\n".join([f"- {item}" for item in items])


def generate_fallback_defenses(recommendation: str, analysis: dict, strategy: dict) -> dict:
    """Generate basic defenses if AI call fails"""

    confidence = float(analysis.get("confidence", 0.5))
    margin = float(strategy.get("unit_economics", {}).get("gross_margin_pct", 0))

    fallbacks = {
        "PROCEED": {
            "why_not_stop": (
                "Market opportunity and demand indicators are positive enough to justify moving forward, "
                "despite execution risks."
            ),
            "why_not_investigate": (
                f"Available data provides {confidence:.0%} confidence - sufficient for action rather than prolonged research."
            ),
        },
        "STOP": {
            "why_not_proceed": (
                f"Unit economics ({margin:.0f}% margin) and competitive dynamics create unfavorable risk-reward profile."
            ),
            "why_not_investigate": (
                "Core business model constraints are clear enough that further research won't change fundamental viability."
            ),
        },
        "INVESTIGATE": {
            "why_not_proceed": (
                f"Current confidence level ({confidence:.0%}) is too low for immediate launch - key uncertainties remain."
            ),
            "why_not_stop": (
                "Sufficient positive indicators exist to warrant targeted validation rather than complete rejection."
            ),
        },
    }

    return fallbacks.get(recommendation, {})
