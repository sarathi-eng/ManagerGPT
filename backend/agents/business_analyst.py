from __future__ import annotations

import asyncio
import ast
import json
import os
import re
from urllib.parse import urlparse
from typing import Any, Optional

import httpx

from .. import database
from ..utils.error_handler import graceful_failure
from ..utils.reasoning_validator import ReasoningValidator
from ..utils.parse_llm_json import parse_llm_json

SYSTEM_PROMPT = """
You are an Expert Business Analyst AI.

CRITICAL REASONING REQUIREMENTS:
❌ NEVER say: "demand seems moderate", "potential exists", "market looks promising"
✅ ALWAYS say: "68% of students game weekly (Source: Statista 2024) → recurring usage viable"

Every claim MUST be anchored to:
1. Specific numbers from research
2. Named sources
3. Logical inference from data

BAD REASONING (REJECT THIS):
"The market potential requires validation"
→ Too vague, no data

GOOD REASONING (DO THIS):
"In-store conversion rate is 4.2% (POS data) while staff utilization peaks at 95% on weekends (internal ops). This creates bottlenecks that threaten service quality. Recommendation: INVESTIGATE scheduling changes tied to utilization." 
→ Specific numbers, sources cited, logical conclusion

FORMATTING RULES:
- Reference actual numbers from research findings
- Cite source name (not URL) inline: "(McKinsey 2024)", "(company SEC filing)"
- Connect data points with logical reasoning
- Quantify whenever possible

Your analysis must read like a professional consulting report, not generic AI text.

Your analysis must include:

1. BUSINESS CLASSIFICATION
     - Business type (B2B, B2C, B2B2C, Marketplace, SaaS, etc.)
     - Business model (Subscription, One-time, Freemium, Licensing, etc.)
     - Target customer profile
     - Customer pain points this solves

2. PROS & CONS ANALYSIS
     - List 5-7 key advantages (pros)
     - List 5-7 key challenges (cons)
     - Be specific and data-driven

3. LONG-TERM SUSTAINABILITY
    - Sustainability score (0-1, where 1 is highly sustainable)
    - Key sustainability factors (operational resilience, defensibility, scalability)
    - Long-term viability: HIGH, MEDIUM, or LOW
    - Reasoning for assessment

4. RECOMMENDATION
     - PROCEED, STOP, or INVESTIGATE
     - Clear reasoning
     - Confidence score (0-1)

Output ONLY valid JSON in this exact format:
{
    "business_classification": {
        "business_type": "B2C SaaS",
        "business_model": "Freemium + Subscription",
        "target_customer": "College students aged 18-24",
        "customer_pain_points": [
            "Difficulty managing meal planning on tight budgets",
            "Limited cooking skills and time"
        ]
    },
    "pros": [
        "Retention at X% indicates recurring usage (Source)",
        "Low customer acquisition cost via social media (Source)",
        "Specific pro with data (Source)"
    ],
    "cons": [
        "High competition from established players (Source)",
        "Low switching costs for customers (Source)",
        "Specific con with impact (Source)"
    ],
    "sustainability": {
        "score": 0.72,
        "factors": [
            "Strong market tailwinds in health tech (Source)",
            "Requires continuous content creation (Source)",
            "Network effects potential is limited (Source)"
        ],
        "long_term_viability": "MEDIUM",
        "reasoning": "Market is growing but competition is intense (Source). Success depends on differentiation and retention."
    },
    "recommendation": "INVESTIGATE",
    "reasoning": "Data-anchored explanation with specific numbers and sources",
    "confidence": 0.68,
    "key_evidence": [
        "Customer metric Z (Source)",
        "Unit economics metric (Source)",
        "Operational constraint metric (Source)"
    ],
    "data_quality_score": 0.85
}
"""

PRIMARY_MODEL = os.getenv("BUSINESS_ANALYST_MODEL", "z-ai/glm-4.5-air:free")
FALLBACK_MODELS = [
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "google/gemma-3-27b-it:free",
    "openrouter/pony-alpha",
]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 1800
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


def _safe_json_loads(raw_text: str) -> dict:
    blob = _extract_json_blob(raw_text)
    try:
        data = parse_llm_json(blob)
        if isinstance(data, dict):
            return data
        raise ValueError("Expected JSON object")
    except Exception:
        cleaned = (
            blob.replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
        )
        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
        try:
            data = parse_llm_json(cleaned)
            if isinstance(data, dict):
                return data
            raise ValueError("Expected JSON object")
        except Exception:
            data = ast.literal_eval(cleaned)
            if isinstance(data, dict):
                return data
            raise ValueError("Expected JSON object")


def _build_user_message(
    research_results: list[dict],
    user_goal: str,
    business_name: Optional[str],
    context: dict | None = None,
) -> str:
    sections = []
    for idx, result in enumerate(research_results, start=1):
        data_points = extract_data_points(result)
        sources = format_sources(result)
        sections.append(
            "Task {idx} - Research Data Points:\n{data_points}\nSources: {sources}\n".format(
                idx=idx,
                data_points=data_points or "- No structured data points found",
                sources=sources or "No sources provided",
            )
        )

    header = f"Original Business Goal: {user_goal}\n"
    if business_name:
        header += f"Existing Business Reference: {business_name}\n"
    if context:
        header += f"Context: {json.dumps(context, ensure_ascii=False)}\n"

    return (
        f"{header}\n"
        "Research Data Points (USE THESE SPECIFIC NUMBERS):\n\n"
        + "\n".join(sections)
        + "\nREQUIREMENTS:\n"
        + "1. Reference at least 5 specific data points from above\n"
        + "2. Cite source names inline\n"
        + "3. Show logical connections between data and conclusion\n"
        + "4. No generic statements - every claim must have evidence\n"
        + "\nUse ONLY the provided research data points and sources."
    )


def extract_data_points(research: dict) -> str:
    """Extract key numbers and facts from research"""
    findings = str(research.get("findings", ""))
    numbers = re.findall(r"\$[\d,\.]+[MBK]?|\d+%|\d+[\.,]\d+", findings)
    sentences = [s.strip() for s in findings.split(".") if s.strip()]
    data_sentences = [s for s in sentences if any(n in s for n in numbers)]
    top_points = data_sentences[:5]
    if not top_points:
        return ""
    return "\n- " + "\n- ".join(top_points)


def format_sources(research: dict) -> str:
    """Format sources with their domain names for citation"""
    sources = []
    for url in (research.get("sources", []) or [])[:3]:
        domain = urlparse(str(url)).netloc.replace("www.", "")
        if domain:
            sources.append(domain)
    return ", ".join(sources)


def _build_research_fallback(research_results: list[dict], user_goal: str) -> dict:
    return {
        "sustainability": {
            "score": 0.45,
            "factors": ["Evidence base is incomplete", "Operational durability unverified"],
            "long_term_viability": "MEDIUM",
            "reasoning": "Research was insufficient to fully validate long-term sustainability.",
        },
        "recommendation": "INVESTIGATE",
        "reasoning": (
            f"Analysis derived from available research. Additional validation required. Goal: {user_goal}"
        ),
        "confidence": 0.35,
    }


def _generate_structured_fallback(user_goal: str, research_results: list[dict]) -> dict:
    return {
        "recommendation": "INVESTIGATE",
        "reasoning": (
            "This opportunity shows potential but requires validation of key assumptions around "
            "customer acquisition costs, competitive positioning, and operational scalability."
        ),
        "confidence": 0.65,
        "sustainability": {
            "score": 0.65,
            "factors": [
                "Operational resilience",
                "Competitive intensity",
                "Execution risk",
            ],
            "long_term_viability": "MEDIUM",
            "reasoning": "Long-term success depends on execution and operational resilience",
        },
    }


async def _call_openrouter(
    system_prompt: str,
    user_message: str,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
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


@graceful_failure("Refining business analysis...")
async def analyze_business_comprehensive(
    research_results: list[dict],
    session_id: int,
    user_goal: str,
    business_name: Optional[str] = None,
    context: dict | None = None,
) -> dict:
    database.log_agent_activity(
        session_id,
        "Business Analyst",
        "Performing comprehensive analysis...",
        "working",
        None,
    )

    def _fallback_analysis(reason: str) -> dict:
        fallback = _build_research_fallback(research_results, user_goal)
        fallback["reasoning"] = reason
        analysis_id = database.save_analysis(
            session_id,
            fallback["recommendation"],
            fallback["reasoning"],
            fallback["confidence"],
        )
        business_id = database.save_business_analysis(session_id, fallback)
        database.log_agent_activity(
            session_id,
            "Business Analyst",
            f"Analysis complete: {fallback['recommendation']}",
            "complete",
            None,
        )
        return {
            "analysis_id": analysis_id or 0,
            "business_analysis_id": business_id or 0,
            **fallback,
        }

    api_key = os.getenv("OPEN_ROUTER_API_KEY")
    if not api_key:
        database.log_agent_activity(
            session_id,
            "Business Analyst",
            "Analysis configuration missing; using default analysis",
            "rejected",
            None,
        )
        return _fallback_analysis(
            "Missing API key and limited analysis. Configure OPEN_ROUTER_API_KEY."
        )

    user_message = _build_user_message(research_results, user_goal, business_name, context)

    models = [PRIMARY_MODEL] + [m for m in FALLBACK_MODELS if m]
    data = None
    for model in models:
        try:
            payload = await _call_openrouter(SYSTEM_PROMPT, user_message, api_key, model)
            content = _extract_content(payload)
            data = _safe_json_loads(content)
            break
        except Exception:  # noqa: BLE001
            database.log_agent_activity(
                session_id,
                "Business Analyst",
                "Analysis service unavailable. Retrying with structured format.",
                "error",
                None,
            )
            try:
                repair_prompt = (
                    "Return ONLY valid JSON using the required schema. "
                    "Do not include markdown or explanations."
                )
                payload = await _call_openrouter(
                    SYSTEM_PROMPT,
                    f"{repair_prompt}\n\n{user_message}",
                    api_key,
                    model,
                )
                content = _extract_content(payload)
                data = _safe_json_loads(content)
                break
            except Exception:  # noqa: BLE001
                continue

    if data is None:
        structured = _generate_structured_fallback(user_goal, research_results)
        structured["reasoning"] = structured.get("reasoning", "").strip()
        analysis_id = database.save_analysis(
            session_id,
            structured["recommendation"],
            structured["reasoning"],
            structured["confidence"],
        )
        business_id = database.save_business_analysis(session_id, structured)
        database.log_agent_activity(
            session_id,
            "Business Analyst",
            f"Analysis complete: {structured['recommendation']}",
            "complete",
            None,
        )
        return {
            "analysis_id": analysis_id or 0,
            "business_analysis_id": business_id or 0,
            **structured,
        }

    recommendation = str(data.get("recommendation", "INVESTIGATE"))
    reasoning = str(data.get("reasoning", ""))[:600]
    confidence = float(data.get("confidence", 0.3))

    reasoning_check = ReasoningValidator.validate_reasoning(reasoning)
    if not reasoning_check["is_strong"]:
        database.log_agent_activity(
            session_id,
            "Quality Check",
            "⚠️ Reasoning quality: {:.0%} - {}".format(
                reasoning_check["score"],
                ", ".join(reasoning_check["issues"]),
            ),
            "warning",
            {
                "issues": reasoning_check["issues"],
                "suggestions": reasoning_check["suggestions"],
            },
        )
        confidence *= reasoning_check["score"]

    if not isinstance(data.get("pros"), list):
        data["pros"] = []
    if not isinstance(data.get("cons"), list):
        data["cons"] = []

    analysis_id = database.save_analysis(session_id, recommendation, reasoning, confidence)
    business_id = database.save_business_analysis(session_id, data)

    database.log_agent_activity(
        session_id,
        "Business Analyst",
        f"Analysis complete: {recommendation}",
        "complete",
        None,
    )

    return {
        "analysis_id": analysis_id or 0,
        "business_analysis_id": business_id or 0,
        **data,
        "recommendation": recommendation,
        "reasoning": reasoning,
        "confidence": confidence,
    }


class BusinessAnalystAgent:
    name = "Business Analyst"

    def analyze(
        self,
        research_results: list[dict],
        session_id: int,
        user_goal: str,
        business_name: Optional[str] = None,
    ) -> dict:
        return asyncio.run(
            analyze_business_comprehensive(research_results, session_id, user_goal, business_name)
        )
