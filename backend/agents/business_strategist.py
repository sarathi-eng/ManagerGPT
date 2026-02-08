from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .. import database
from ..utils.parse_llm_json import parse_llm_json

SYSTEM_PROMPT = """
You are an Expert Business Strategist and CFO AI.

Given a business analysis, provide ACTIONABLE strategic metrics:

1. BREAK-EVEN ANALYSIS
   - Estimate breakeven timeframe (months)
   - Identify key driver (what determines success)
   - List critical assumptions

2. CUSTOMER SEGMENT FIT
   - Primary segment (most likely buyers)
   - Segment size estimate
   - Secondary segments
   - Poor fit segments (who NOT to target)
   - Why each segment fits/doesn't fit

3. PRICING FEASIBILITY
   - Optimal price range
   - Price sensitivity (HIGH/MEDIUM/LOW)
   - Specific price points with viability assessment
   - Price elasticity reasoning

4. ADOPTION THRESHOLD (Go/No-Go Metric)
   - Minimum adoption % needed for viability
   - Failure threshold (below this % = pivot/stop)
   - How to measure this KPI
   - Timeline for measurement

5. UNIT ECONOMICS
   - Cost per unit/transaction
   - Revenue per unit/transaction
   - Gross margin %
   - Health assessment (STRONG/ACCEPTABLE/WEAK)
   - Margin buffer level (HIGH/MEDIUM/LOW)

6. LAUNCH STRATEGY
   - Recommended approach (Focused/Gradual/Broad)
   - Specific launch steps (3-5 actionable steps)
   - Timeline in days
   - Success criteria for each step

7. EARLY FAILURE SIGNALS
   - Metrics to track in first 2-4 weeks
   - Red flags that indicate pivot needed
   - Timeframe for each signal

8. COMPARABLE CASES
   - 2-3 similar businesses (with outcomes)
   - What they did right/wrong
   - Key lessons

9. RESOURCE REQUIREMENTS
   - Operational complexity level
   - Time commitment level
   - Automation potential
   - Critical skills needed

10. PIVOT SUGGESTIONS (if recommendation is STOP/INVESTIGATE)
    - 2-3 alternative approaches
    - Why each might work better
    - Required changes

Be SPECIFIC. Use numbers. Make it actionable.

Output ONLY valid JSON matching the required structure.
"""

MODEL = os.getenv("BUSINESS_STRATEGIST_MODEL", "z-ai/glm-4.5-air:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 2000
TEMPERATURE = 0.3


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    return cleaned.strip()


def _extract_json_blob(text: str) -> str:
    cleaned = _strip_code_fences(text)
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


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


def _format_research_for_context(research_results: list[dict]) -> str:
    output: list[str] = []
    for idx, result in enumerate(research_results, start=1):
        output.append(f"Research Area {idx}:")
        output.append(str(result.get("findings", "")))
        sources = ", ".join([str(src) for src in result.get("sources", [])[:3]])
        output.append(f"Sources: {sources}")
        output.append("")
    return "\n".join(output)


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


async def generate_business_strategy(
    business_analysis: dict,
    research_results: list[dict],
    session_id: int,
    user_goal: str,
) -> dict:
    database.log_agent_activity(
        session_id,
        "Business Strategist",
        "Developing execution strategy and metrics...",
        "working",
        None,
    )

    api_key = os.getenv("OPEN_ROUTER_API_KEY")
    if not api_key:
        database.log_agent_activity(
            session_id,
            "Business Strategist",
            "Missing OPEN_ROUTER_API_KEY",
            "error",
            None,
        )
        return {}

    user_message = (
        f"Original Business Goal: {user_goal}\n\n"
        "Business Analysis Summary:\n"
        f"- Recommendation: {business_analysis.get('recommendation')}\n"
        f"- Business Type: {business_analysis.get('business_classification', {}).get('business_type')}\n"
        f"- Target Customer: {business_analysis.get('business_classification', {}).get('target_customer')}\n"
        f"- Pros: {json.dumps(business_analysis.get('pros', [])[:3])}\n"
        f"- Cons: {json.dumps(business_analysis.get('cons', [])[:3])}\n"
        f"- Investment Range: {business_analysis.get('investment', {}).get('min', 0):,.0f}"
        f" - {business_analysis.get('investment', {}).get('max', 0):,.0f}\n\n"
        "Research Findings:\n"
        f"{_format_research_for_context(research_results)}\n"
        "Generate comprehensive business strategy with specific, actionable metrics."
    )

    try:
        payload = await _call_openrouter(SYSTEM_PROMPT, user_message, api_key)
        content = _extract_content(payload)
        strategy = parse_llm_json(_extract_json_blob(content))
        if not isinstance(strategy, dict):
            raise ValueError("Invalid strategy payload")

        database.save_business_metrics(session_id, strategy)
        breakeven = strategy.get("breakeven", {}) or {}
        database.log_agent_activity(
            session_id,
            "Business Strategist",
            (
                "Strategy complete: Break-even in "
                f"{breakeven.get('months_min')}"
                f"-{breakeven.get('months_max')} months"
            ),
            "complete",
            None,
        )
        return strategy
    except Exception as exc:  # noqa: BLE001
        database.log_agent_activity(
            session_id,
            "Business Strategist",
            f"Error: {exc}",
            "error",
            None,
        )
        return {}