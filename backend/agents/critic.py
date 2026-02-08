from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Optional

import httpx

from .. import database
from ..utils.parse_llm_json import parse_llm_json

SYSTEM_PROMPT = (
    "You are a Critical Evaluator AI. Your job is to find flaws in analysis and reasoning.\n\n"
    "Be skeptical. Look for:\n- Weak or unreliable sources\n- Logical fallacies\n- Unsupported assumptions\n"
    "- Missing critical data\n- Overconfidence\n- Contradictions between research and conclusions\n\n"
    "If the analysis is solid, approve it.\nIf there are significant issues, reject it and "
    "specify what needs improvement.\n\nOutput ONLY valid JSON:\n{\n  \"approved\": true|false,\n  "
    "\"issues\": [\n    \"Specific issue 1 with explanation\",\n    \"Specific issue 2 with explanation\"\n  ],\n"
    "  \"confidence_adjustment\": -0.15,\n  \"severity\": \"MINOR|MODERATE|SEVERE\",\n  \"requires_retry\": true|false\n}"
)

MODEL = os.getenv("CRITIC_MODEL", "z-ai/glm-4.5-air:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 900
TEMPERATURE = 0.2


def _format_research_summary(research_results: list[dict]) -> str:
    lines: list[str] = []
    for idx, item in enumerate(research_results, start=1):
        lines.append(f"Task {idx} Findings: {item.get('findings')}")
        lines.append(f"Sources: {item.get('sources')}")
    return "\n".join(lines)


def _build_prompt(analysis: dict, research_results: list[dict]) -> str:
    return (
        "Analysis to Review:\n"
        f"Recommendation: {analysis.get('recommendation')}\n"
        f"Reasoning: {analysis.get('reasoning')}\n"
        f"Confidence: {analysis.get('confidence')}\n\n"
        "Supporting Research:\n"
        f"{_format_research_summary(research_results)}\n\n"
        "Critically evaluate this analysis. Find weaknesses, unsupported claims, or logical flaws."
    )


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
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def _normalize_output(data: dict) -> dict:
    approved = bool(data.get("approved", False))
    issues = data.get("issues", []) if isinstance(data.get("issues"), list) else []
    confidence_adjustment = float(data.get("confidence_adjustment", 0))
    severity = str(data.get("severity", "MINOR")).upper()
    if severity not in {"MINOR", "MODERATE", "SEVERE"}:
        severity = "MINOR"
    requires_retry = bool(data.get("requires_retry", not approved))
    return {
        "approved": approved,
        "issues": [str(item) for item in issues],
        "confidence_adjustment": confidence_adjustment,
        "severity": severity,
        "requires_retry": requires_retry,
    }


def reasoning_guardrails(analysis_text: str) -> list[str]:
    violations = []
    if "Blackberry" in analysis_text:
        violations.append("Cross-industry analogy detected")
    if re.search(r"\b\d+%|\b\d+ months|₹\d+", analysis_text):
        violations.append("Unverified numeric claims")
    if "global market size" in analysis_text.lower():
        violations.append("Irrelevant macro statistics")
    return violations


def detect_generic_consulting_speech(text: str) -> bool:
    banned_patterns = [
        "global market",
        "industry revenue",
        "world bank",
        "technology shift",
        "smartphone",
        "market leaders",
        "historical example",
    ]
    lowered = text.lower()
    for pattern in banned_patterns:
        if pattern in lowered:
            return True
    return False


def detect_template_output(text: str) -> bool:
    phrases = [
        "service business shows potential",
        "competitive landscape requires analysis",
        "customer acquisition strategy",
        "scalability potential",
    ]
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def _build_industry_context(analysis: dict) -> str:
    classification = analysis.get("business_classification", {}) or {}
    parts = [
        str(classification.get("business_type", "")),
        str(classification.get("business_model", "")),
        str(classification.get("target_customer", "")),
        " ".join(classification.get("customer_pain_points", []) or []),
        str(analysis.get("reasoning", "")),
    ]
    return " ".join([p for p in parts if p]).lower()


def _competitors_unrelated(competitors: list[dict], industry_context: str) -> bool:
    if not competitors:
        return False

    generic_markers = ["established", "emerging", "diy", "self-service", "traditional", "substitute"]
    context_tokens = {token for token in industry_context.split() if len(token) >= 4}
    unrelated_count = 0
    checked = 0

    for comp in competitors:
        name = str(comp.get("competitor_name", "")).lower()
        if any(marker in name for marker in generic_markers):
            continue
        text = " ".join(
            [
                name,
                str(comp.get("market_position", "")).lower(),
                " ".join(comp.get("strengths", []) or []).lower(),
                " ".join(comp.get("weaknesses", []) or []).lower(),
            ]
        )
        checked += 1
        if not any(token in text for token in context_tokens):
            unrelated_count += 1

    if checked == 0:
        return False
    return unrelated_count == checked


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


async def critique_analysis(
    analysis: dict,
    research_results: list[dict],
    session_id: int,
    competitors: Optional[list[dict]] = None,
) -> dict:
    database.log_agent_activity(
        session_id,
        "Critic",
        "Evaluating analysis quality...",
        "working",
        None,
    )

    analysis_id = int(analysis.get("analysis_id", 0))
    analysis_confidence = float(analysis.get("confidence", 0))

    reasoning_text = str(analysis.get("reasoning", ""))

    if detect_template_output(reasoning_text):
        return {
            "approved": False,
            "issues": ["Template-style output detected"],
            "requires_retry": True,
            "confidence_adjustment": -0.3,
            "severity": "SEVERE",
        }

    if detect_generic_consulting_speech(reasoning_text):
        return {
            "approved": False,
            "issues": ["Non-operational reasoning detected"],
            "requires_retry": True,
            "confidence_adjustment": -0.3,
            "severity": "SEVERE",
        }

    guardrail_violations = reasoning_guardrails(reasoning_text)
    if guardrail_violations:
        result = {
            "approved": False,
            "issues": guardrail_violations,
            "confidence_adjustment": -0.25,
            "severity": "SEVERE",
            "requires_retry": True,
        }
        database.log_agent_activity(
            session_id,
            "Critic",
            "Analysis REJECTED - Reasoning guardrails violated",
            "rejected",
            None,
        )
        database.save_critique(
            analysis_id,
            result["approved"],
            result["issues"],
            result["confidence_adjustment"],
        )
        return result

    if competitors and _competitors_unrelated(competitors, _build_industry_context(analysis)):
        result = {
            "approved": False,
            "issues": ["Competitors appear unrelated to the industry context"],
            "confidence_adjustment": -0.2,
            "severity": "SEVERE",
            "requires_retry": True,
        }
        database.log_agent_activity(
            session_id,
            "Critic",
            "Analysis REJECTED - Competitors unrelated to industry",
            "rejected",
            None,
        )
        database.save_critique(
            analysis_id,
            result["approved"],
            result["issues"],
            result["confidence_adjustment"],
        )
        return result

    if analysis_confidence < 0.6:
        result = {
            "approved": True,
            "issues": [],
            "confidence_adjustment": 0.0,
            "severity": "MINOR",
            "requires_retry": False,
        }
        database.log_agent_activity(session_id, "Critic", "Analysis APPROVED", "complete", None)
        database.save_critique(
            analysis_id,
            result["approved"],
            result["issues"],
            result["confidence_adjustment"],
        )
        return result

    api_key = os.getenv("OPEN_ROUTER_API_KEY")
    prompt = _build_prompt(analysis, research_results)

    try:
        if not api_key:
            raise RuntimeError("Missing OPEN_ROUTER_API_KEY")
        payload = await _call_openrouter(prompt, api_key)
        content = _extract_content(payload)
        data = parse_llm_json(_extract_json_blob(content))
    except Exception as exc:  # noqa: BLE001
        database.log_agent_activity(
            session_id,
            "Critic",
            "Critique failed; returning safe defaults.",
            "rejected",
            None,
        )
        data = {
            "approved": False,
            "issues": ["Critique failed; unable to validate analysis"],
            "confidence_adjustment": -0.1,
            "severity": "MODERATE",
            "requires_retry": True,
        }

    result = _normalize_output(data)

    if analysis_confidence > 0.8 and abs(result["confidence_adjustment"]) < 0.2:
        result["approved"] = False
        result["issues"].append("Confidence appears too high compared to evidence")
        result["confidence_adjustment"] = min(result["confidence_adjustment"], -0.2)
        result["severity"] = "SEVERE"
        result["requires_retry"] = True

    severe_count = sum(1 for issue in result["issues"] if "severe" in issue.lower())
    if severe_count > 2:
        result["approved"] = False
        result["severity"] = "SEVERE"
        result["requires_retry"] = True

    if result["approved"]:
        database.log_agent_activity(session_id, "Critic", "Analysis APPROVED", "complete", None)
    else:
        database.log_agent_activity(session_id, "Critic", "Analysis REJECTED - Issues found", "rejected", None)

    database.save_critique(
        analysis_id,
        result["approved"],
        result["issues"],
        result["confidence_adjustment"],
    )
    return result


class CriticAgent:
    name = "Critic"

    def critique(self, analysis: dict, research_results: list[dict], session_id: int) -> dict:
        return asyncio.run(critique_analysis(analysis, research_results, session_id))
