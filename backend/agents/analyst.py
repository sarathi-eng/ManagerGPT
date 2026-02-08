from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import httpx

from .. import database
from .mechanism import extract_mechanism
from ..utils.safe_json import safe_load_json
from ..utils.parse_llm_json import parse_llm_json

SYSTEM_PROMPT = "Return only valid JSON."

MODEL = "z-ai/glm-4.5-air:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 1500
TEMPERATURE = 0.3


def _build_prompt(
    research_text: str,
    context: dict,
    mechanism: dict,
) -> str:
    prompt = f"""
You are a business decision analyst.

Business Context:
Type: {context['business_type']}
Industry: {context['industry']}

Operational Mechanism:
{mechanism['core_mechanism']}

Variables affected:
{mechanism['affected_variables']}

Evidence:
{research_text}

CRITICAL RULES:
- Reason ONLY using the operational mechanism
- Ignore global statistics
- Ignore other industries
- Do not invent numbers
- Only numbers explicitly present in evidence may be used
- If evidence weak → CONDITIONAL decision
- Keep explanation under 100 words

Return JSON:
{{
 "recommendation": "PROCEED|STOP|CONDITIONAL",
 "reasoning": "short explanation tied to mechanism",
 "confidence": 0-1,
 "primary_risk": "main operational risk",
 "required_validation": "what must be tested"
}}
"""
    return prompt


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


def _validate_recommendation(value: str) -> bool:
    return value in {"PROCEED", "STOP", "CONDITIONAL"}


def strip_fake_numbers(text: str) -> str:
    return re.sub(r"\b\d+%|\b\d+\s*(months|days|weeks)|₹\d+", "[unverified]", text)


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


async def _call_openrouter_messages(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 800,
        "temperature": 0,
    }
    timeout_seconds = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "20"))
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(OPENROUTER_URL, headers=headers, json=body)
        response.raise_for_status()
        return response.json()


async def extract_decision_axis(
    context: dict | None,
    research_text: str,
    user_goal: str,
    api_key: str,
) -> dict:
    context_payload = context or {}
    prompt = (
        "You are a senior business strategist.\n\n"
        "Goal:\n"
        f"{user_goal}\n\n"
        "Industry:\n"
        f"{context_payload.get('industry', 'unknown')}\n\n"
        "Research:\n"
        f"{research_text}\n\n"
        "Task:\n"
        "Identify the SINGLE core economic tradeoff that determines this decision.\n\n"
        "Rules:\n"
        "- Do NOT give advice\n"
        "- Do NOT conclude\n"
        "- Do NOT add numbers\n"
        "- Only describe the decision axis\n\n"
        "Examples:\n"
        "Gym pricing → revenue stability vs utilization volatility\n"
        "Cloud kitchen → delivery density vs fixed rent cost\n"
        "Subscription SaaS → acquisition cost vs lifetime value\n\n"
        "Return JSON:\n"
        "{\n"
        "  \"decision_axis\": \"short phrase\",\n"
        "  \"explanation\": \"1-2 sentence explanation\"\n"
        "}"
    )
    try:
        payload = await _call_openrouter_messages(
            "Return only valid JSON.",
            prompt,
            api_key,
        )
        content = _extract_content(payload)
        data = parse_llm_json(_extract_json_blob(content))
        if isinstance(data, dict) and data.get("decision_axis"):
            return data
    except Exception:  # noqa: BLE001
        pass

    return {
        "decision_axis": "Evidence strength vs execution risk",
        "explanation": "Decision hinges on whether the evidence base is strong enough to justify execution risk.",
    }


async def analyze_findings(
    research_results: list[dict],
    session_id: int,
    user_goal: str,
    context: dict | None = None,
) -> dict:
    database.log_agent_activity(
        session_id,
        "Analyst",
        "Analyzing research findings...",
        "working",
        None,
    )

    api_key = os.getenv("OPEN_ROUTER_API_KEY")
    if not api_key:
        database.log_agent_activity(
            session_id,
            "Analyst",
            "Missing OPEN_ROUTER_API_KEY, using default analysis",
            "rejected",
            None,
        )
        analysis_id = database.save_analysis(session_id, "CONDITIONAL", "Missing API key", 0.3)
        database.log_agent_activity(
            session_id,
            "Analyst",
            "Recommendation: CONDITIONAL",
            "complete",
            None,
        )
        return {
            "analysis_id": analysis_id or 0,
            "recommendation": "CONDITIONAL",
            "reasoning": "Missing API key",
            "confidence": 0.3,
            "primary_risk": "Model call unavailable without API key",
            "required_validation": "Configure OPEN_ROUTER_API_KEY and rerun analysis",
        }

    compiled_research = "\n\n".join(
        [str(item.get("findings", "")).strip() for item in research_results if item.get("findings")]
    )
    compiled_research = compiled_research or "No research findings provided."

    context = context or {"business_type": "unknown", "industry": "unknown"}

    try:
        mechanism = await extract_mechanism(user_goal, context)
        if not isinstance(mechanism, dict):
            raise ValueError("Mechanism returned non-dict")
    except Exception:  # noqa: BLE001
        mechanism = {
            "core_mechanism": "Operational changes are unclear due to limited evidence.",
            "affected_variables": ["revenue stability", "labor utilization", "capacity usage"],
        }

    prompt = _build_prompt(compiled_research, context, mechanism)

    try:
        payload = await _call_openrouter(prompt, api_key)
        content = _extract_content(payload)
        data = safe_load_json(_extract_json_blob(content)) or safe_load_json(content)
        if data is None:
            data = {
                "recommendation": "CONDITIONAL",
                "reasoning": (
                    "Available evidence insufficient; decision depends on operational risk "
                    "tolerance and frequency of urgent demand."
                ),
                "confidence": 0.2,
                "primary_risk": "unknown demand variability",
                "required_validation": "track real usage frequency of rarely stocked items",
            }
    except Exception as exc:  # noqa: BLE001
        database.log_agent_activity(
            session_id,
            "Analyst",
            f"Analysis failed: {exc}",
            "rejected",
            None,
        )
        has_sources = any(result.get("sources") for result in research_results)
        recommendation = "CONDITIONAL" if not has_sources else "PROCEED"
        reasoning = (
            "Fallback analysis based on available research results. "
            "Recommendation is provisional pending stronger evidence."
        )[:600]
        confidence = 0.35 if not has_sources else 0.55
        analysis_id = database.save_analysis(session_id, recommendation, reasoning, confidence)
        database.log_agent_activity(
            session_id,
            "Analyst",
            f"Recommendation: {recommendation}",
            "complete",
            None,
        )
        return {
            "analysis_id": analysis_id or 0,
            "recommendation": recommendation,
            "reasoning": reasoning,
            "confidence": confidence,
            "primary_risk": "Evidence base too weak to quantify impact reliably",
            "required_validation": "Collect operational evidence tied to the mechanism",
        }

    recommendation = str(data.get("recommendation", "CONDITIONAL"))
    reasoning = str(data.get("reasoning", ""))[:600]
    reasoning = strip_fake_numbers(reasoning)
    confidence = float(data.get("confidence", 0.3))
    primary_risk = str(data.get("primary_risk", ""))
    required_validation = str(data.get("required_validation", ""))

    if not _validate_recommendation(recommendation) or not (0 <= confidence <= 1):
        database.log_agent_activity(
            session_id,
            "Analyst",
            "Invalid analysis output, using default",
            "rejected",
            None,
        )
        recommendation = "CONDITIONAL"
        reasoning = "Invalid analysis output"
        confidence = 0.3
        primary_risk = "Evidence format invalid"
        required_validation = "Retry analysis with validated evidence"

    analysis_id = database.save_analysis(session_id, recommendation, reasoning, confidence)
    database.log_agent_activity(
        session_id,
        "Analyst",
        f"Recommendation: {recommendation}",
        "complete",
        None,
    )

    return {
        "analysis_id": analysis_id or 0,
        "recommendation": recommendation,
        "reasoning": reasoning,
        "confidence": confidence,
        "primary_risk": primary_risk,
        "required_validation": required_validation,
    }


class AnalystAgent:
    name = "Analyst"

    def analyze(
        self,
        research_results: list[dict],
        session_id: int,
        user_goal: str,
        context: dict | None = None,
    ) -> dict:
        return asyncio.run(analyze_findings(research_results, session_id, user_goal, context))
