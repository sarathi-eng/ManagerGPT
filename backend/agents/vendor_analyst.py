from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Optional

import httpx

from .. import database
from ..utils.json_parser import clean_json_response
from ..utils.parse_llm_json import parse_llm_json

SYSTEM_PROMPT = """
You are a Supply Chain & Vendor Analysis AI.

For each vendor/supplier/technology partner, analyze:
1. Vendor type (Technology provider, Manufacturing, Distribution, Payment, etc.)
2. Importance level (CRITICAL, IMPORTANT, OPTIONAL)
3. Advantages of using this vendor (3-5 points)
4. Disadvantages or risks (3-5 points)
5. Whether viable alternatives exist
6. Switching cost (HIGH, MEDIUM, LOW)

Focus on practical business considerations.

Output ONLY valid JSON array:
[
  {
    "vendor_name": "Stripe",
    "vendor_type": "Payment Processing",
    "importance": "CRITICAL",
    "advantages": [
      "Easy integration with extensive documentation",
      "99.99% uptime SLA",
      "Supports 135+ currencies",
      "Strong fraud prevention"
    ],
    "disadvantages": [
      "2.9% + $0.30 per transaction fee",
      "Account freezes can happen without warning",
      "Limited customization for complex workflows"
    ],
    "alternatives_available": true,
    "alternative_examples": ["PayPal, Square, Braintree"],
    "switching_cost": "MEDIUM"
  }
]
"""

logger = logging.getLogger(__name__)

MODEL = os.getenv("VENDOR_ANALYST_MODEL", "z-ai/glm-4.5-air:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 1400
TEMPERATURE = 0.3
TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")


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


async def _call_tavily(query: str, api_key: str) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    body = {
        "api_key": api_key,
        "query": query,
        "search_depth": os.getenv("TAVILY_SEARCH_DEPTH", "basic"),
        "max_results": int(os.getenv("TAVILY_MAX_RESULTS_LARGE", "5")),
    }
    async with httpx.AsyncClient(timeout=40) as client:
        response = await client.post(f"{TAVILY_BASE_URL}/search", headers=headers, json=body)
        response.raise_for_status()
        return response.json()


def _build_research_context(payload: Optional[dict[str, Any]]) -> str:
    if not payload or not isinstance(payload.get("results"), list):
        return ""
    snippets = []
    for item in payload.get("results", []):
        content = item.get("content")
        url = item.get("url")
        if content:
            snippets.append(f"- {content} ({url})")
    return "\n".join(snippets)


async def _call_llm_with_optional_search(
    system_prompt: str,
    user_message: str,
    search_query: str,
    api_key: str,
    tavily_key: Optional[str],
) -> str:
    research_context = ""
    if tavily_key:
        try:
            payload = await _call_tavily(search_query, tavily_key)
            research_context = _build_research_context(payload)
        except Exception:
            research_context = ""

    if research_context:
        user_message = f"{user_message}\n\nWeb Research Snippets:\n{research_context}"

    payload = await _call_openrouter(system_prompt, user_message, api_key)
    return _extract_content(payload)


async def analyze_vendors(
    business_context: str,
    vendor_names: list[str],
    session_id: int,
) -> list[dict]:
    database.log_agent_activity(
        session_id,
        "Vendor Analyst",
        "Analyzing vendors and suppliers...",
        "working",
        None,
    )

    api_key = os.getenv("OPEN_ROUTER_API_KEY")
    tavily_key = os.getenv("TAVILY_API_KEY")

    try:
        if vendor_names:
            vendors = await analyze_specific_vendors(
                business_context,
                vendor_names,
                session_id,
                api_key,
                tavily_key,
            )
            if vendors:
                for vendor in vendors:
                    database.save_vendor(session_id, vendor)
                database.log_agent_activity(
                    session_id,
                    "Vendor Analyst",
                    f"Analyzed {len(vendors)} vendors",
                    "complete",
                    None,
                )
                return vendors

        database.log_agent_activity(
            session_id,
            "Vendor Analyst",
            "Identifying critical vendors...",
            "working",
            None,
        )
        vendors = await identify_and_analyze_vendors(
            business_context,
            session_id,
            api_key,
            tavily_key,
        )
        if vendors:
            for vendor in vendors:
                database.save_vendor(session_id, vendor)
            database.log_agent_activity(
                session_id,
                "Vendor Analyst",
                f"Identified {len(vendors)} vendors",
                "complete",
                None,
            )
            return vendors

        database.log_agent_activity(
            session_id,
            "Vendor Analyst",
            "Generating vendor categories...",
            "working",
            None,
        )
        vendors = await generate_category_vendors(
            business_context,
            session_id,
            api_key,
        )
        if vendors:
            for vendor in vendors:
                database.save_vendor(session_id, vendor)
            database.log_agent_activity(
                session_id,
                "Vendor Analyst",
                f"Generated {len(vendors)} vendor categories",
                "complete",
                None,
            )
            return vendors

        database.log_agent_activity(
            session_id,
            "Vendor Analyst",
            "Completing vendor overview...",
            "complete",
            None,
        )
        fallback = generate_fallback_vendors(business_context)
        for vendor in fallback:
            database.save_vendor(session_id, vendor)
        return fallback
    except Exception as exc:  # noqa: BLE001
        logger.error("Vendor analysis error: %s", exc)
        database.log_agent_activity(
            session_id,
            "Vendor Analyst",
            "Completing vendor overview...",
            "complete",
            None,
        )
        fallback = generate_fallback_vendors(business_context)
        for vendor in fallback:
            database.save_vendor(session_id, vendor)
        return fallback


async def analyze_specific_vendors(
    business_context: str,
    vendor_names: list[str],
    session_id: int,
    api_key: Optional[str],
    tavily_key: Optional[str],
) -> Optional[list[dict]]:
    system_prompt = """
You are a Supply Chain & Vendor Analysis AI.

For each vendor provided, analyze:
1. Vendor type (Technology provider, Manufacturing, Distribution, Payment, etc.)
2. Importance level (CRITICAL, IMPORTANT, OPTIONAL)
3. Advantages (3-5 points)
4. Disadvantages or risks (3-5 points)
5. Whether viable alternatives exist
6. Switching cost (HIGH, MEDIUM, LOW)

Output ONLY valid JSON array.
"""

    user_message = (
        f"Business Context: {business_context}\n\n"
        f"Analyze these specific vendors/suppliers: {', '.join(vendor_names)}"
    )

    if not api_key:
        return None

    try:
        search_query = f"vendor analysis {', '.join(vendor_names)} for {business_context}"
        result_text = await _call_llm_with_optional_search(
            system_prompt,
            user_message,
            search_query,
            api_key,
            tavily_key,
        )
        vendors = parse_llm_json(clean_json_response(result_text))
        if not isinstance(vendors, list) or not vendors:
            return None

        validated = []
        for vendor in vendors:
            if "vendor_name" in vendor:
                vendor.setdefault("vendor_type", "Service Provider")
                vendor.setdefault("importance", "IMPORTANT")
                vendor.setdefault("advantages", ["Operational support", "Established reliability"])
                vendor.setdefault("disadvantages", ["Pricing sensitivity", "Dependency risk"])
                vendor.setdefault("alternatives_available", True)
                vendor.setdefault("alternative_examples", [])
                vendor.setdefault("switching_cost", "MEDIUM")
                validated.append(vendor)

        return validated or None
    except Exception as exc:  # noqa: BLE001
        logger.error("Specific vendor analysis failed: %s", exc)
        return None


async def identify_and_analyze_vendors(
    business_context: str,
    session_id: int,
    api_key: Optional[str],
    tavily_key: Optional[str],
) -> Optional[list[dict]]:
    system_prompt = """
You are a Supply Chain & Vendor Analysis AI.

Identify 3-5 critical vendors, suppliers, or technology partners this business would need.
Consider payment processors, cloud infrastructure, manufacturing, distribution, etc.

Output ONLY valid JSON array.
"""

    user_message = (
        f"Business Context: {business_context}\n\n"
        "Identify 3-5 critical vendors, suppliers, or technology partners this business would need."
    )

    if not api_key:
        return None

    try:
        search_query = f"critical vendors for {business_context}"
        result_text = await _call_llm_with_optional_search(
            system_prompt,
            user_message,
            search_query,
            api_key,
            tavily_key,
        )
        vendors = parse_llm_json(clean_json_response(result_text))
        if not isinstance(vendors, list) or not vendors:
            return None

        validated = []
        for vendor in vendors:
            if "vendor_name" in vendor:
                vendor.setdefault("vendor_type", "Service Provider")
                vendor.setdefault("importance", "IMPORTANT")
                vendor.setdefault("advantages", ["Operational support", "Established reliability"])
                vendor.setdefault("disadvantages", ["Pricing sensitivity", "Dependency risk"])
                vendor.setdefault("alternatives_available", True)
                vendor.setdefault("alternative_examples", [])
                vendor.setdefault("switching_cost", "MEDIUM")
                validated.append(vendor)

        return validated or None
    except Exception as exc:  # noqa: BLE001
        logger.error("Vendor identification failed: %s", exc)
        return None


async def generate_category_vendors(
    business_context: str,
    session_id: int,
    api_key: Optional[str],
) -> Optional[list[dict]]:
    system_prompt = """
You are a Supply Chain & Vendor Analysis AI.

Instead of specific vendors, identify vendor categories required for this business.
Output ONLY valid JSON array.
"""

    user_message = (
        f"Business Context: {business_context}\n\n"
        "Identify 2-3 vendor categories (not specific companies)."
    )

    if not api_key:
        return None

    try:
        payload = await _call_openrouter(system_prompt, user_message, api_key)
        result_text = _extract_content(payload)
        vendors = parse_llm_json(clean_json_response(result_text))
        if isinstance(vendors, list) and vendors:
            return vendors
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error("Vendor category generation failed: %s", exc)
        return None


def generate_fallback_vendors(business_context: str) -> list[dict]:
    lowered = (business_context or "").lower()
    if "food" in lowered or "delivery" in lowered:
        return [
            {
                "vendor_name": "Payment Processing",
                "vendor_type": "Payments",
                "importance": "CRITICAL",
                "advantages": ["Fast settlement", "Fraud protection"],
                "disadvantages": ["Transaction fees", "Chargeback risk"],
                "alternatives_available": True,
                "alternative_examples": ["Stripe", "PayPal"],
                "switching_cost": "MEDIUM",
            },
            {
                "vendor_name": "Delivery Logistics",
                "vendor_type": "Distribution",
                "importance": "CRITICAL",
                "advantages": ["Coverage across zones", "Route optimization"],
                "disadvantages": ["Variable costs", "Service-level variability"],
                "alternatives_available": True,
                "alternative_examples": ["3PL partners", "In-house fleet"],
                "switching_cost": "HIGH",
            },
            {
                "vendor_name": "Cloud Infrastructure",
                "vendor_type": "Technology",
                "importance": "IMPORTANT",
                "advantages": ["Scalability", "Reliability"],
                "disadvantages": ["Vendor lock-in", "Ongoing costs"],
                "alternatives_available": True,
                "alternative_examples": ["AWS", "GCP", "Azure"],
                "switching_cost": "MEDIUM",
            },
        ]

    if "software" in lowered or "app" in lowered:
        return [
            {
                "vendor_name": "Cloud Infrastructure",
                "vendor_type": "Technology",
                "importance": "CRITICAL",
                "advantages": ["Scalability", "Security controls"],
                "disadvantages": ["Usage-based costs", "Vendor lock-in"],
                "alternatives_available": True,
                "alternative_examples": ["AWS", "GCP", "Azure"],
                "switching_cost": "MEDIUM",
            },
            {
                "vendor_name": "Payment Processing",
                "vendor_type": "Payments",
                "importance": "IMPORTANT",
                "advantages": ["Global coverage", "Subscription billing"],
                "disadvantages": ["Fees", "Compliance overhead"],
                "alternatives_available": True,
                "alternative_examples": ["Stripe", "Adyen"],
                "switching_cost": "MEDIUM",
            },
            {
                "vendor_name": "Analytics & Monitoring",
                "vendor_type": "Technology",
                "importance": "IMPORTANT",
                "advantages": ["Product insights", "Issue detection"],
                "disadvantages": ["Data tooling costs", "Complex setup"],
                "alternatives_available": True,
                "alternative_examples": ["Datadog", "Mixpanel"],
                "switching_cost": "LOW",
            },
        ]

    return [
        {
            "vendor_name": "Operational Services",
            "vendor_type": "Services",
            "importance": "IMPORTANT",
            "advantages": ["Reliability", "Service coverage"],
            "disadvantages": ["Cost variability", "Quality differences"],
            "alternatives_available": True,
            "alternative_examples": ["Regional providers", "In-house"],
            "switching_cost": "MEDIUM",
        },
        {
            "vendor_name": "Technology Platform",
            "vendor_type": "Technology",
            "importance": "IMPORTANT",
            "advantages": ["Scalability", "Automation"],
            "disadvantages": ["Integration work", "Ongoing fees"],
            "alternatives_available": True,
            "alternative_examples": ["Vendor A", "Vendor B"],
            "switching_cost": "MEDIUM",
        },
    ]


class VendorAnalystAgent:
    name = "Vendor Analyst"

    def analyze(
        self,
        business_context: str,
        vendor_names: list[str],
        session_id: int,
    ) -> list[dict]:
        return asyncio.run(analyze_vendors(business_context, vendor_names, session_id))
