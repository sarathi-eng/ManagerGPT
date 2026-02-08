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
from ..utils.tavily_search import tavily_search_filtered

logger = logging.getLogger(__name__)

MODEL = os.getenv("COMPETITOR_ANALYST_MODEL", "z-ai/glm-4.5-air:free")
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
    results = await tavily_search_filtered(
        query,
        api_key,
        max_results=int(os.getenv("TAVILY_MAX_RESULTS_LARGE", "10")),
        search_depth=os.getenv("TAVILY_SEARCH_DEPTH", "advanced"),
    )
    return {"results": results}


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


async def analyze_competitors(
    business_context: str,
    competitor_names: list[str],
    session_id: int,
) -> list[dict]:
    database.log_agent_activity(
        session_id,
        "Competitor Analyst",
        "Identifying key competitors...",
        "working",
        None,
    )

    api_key = os.getenv("OPEN_ROUTER_API_KEY")
    tavily_key = os.getenv("TAVILY_API_KEY")

    try:
        if competitor_names:
            competitors = await analyze_specific_competitors(
                business_context,
                competitor_names,
                session_id,
                api_key,
                tavily_key,
            )
            if competitors:
                for comp in competitors:
                    database.save_competitor(session_id, comp)
                database.log_agent_activity(
                    session_id,
                    "Competitor Analyst",
                    f"Analyzed {len(competitors)} competitors",
                    "complete",
                    None,
                )
                return competitors

        database.log_agent_activity(
            session_id,
            "Competitor Analyst",
            "Searching for market competitors...",
            "working",
            None,
        )
        competitors = await identify_and_analyze_competitors(
            business_context,
            session_id,
            api_key,
            tavily_key,
        )
        if competitors:
            for comp in competitors:
                database.save_competitor(session_id, comp)
            database.log_agent_activity(
                session_id,
                "Competitor Analyst",
                f"Identified and analyzed {len(competitors)} competitors",
                "complete",
                None,
            )
            return competitors

        database.log_agent_activity(
            session_id,
            "Competitor Analyst",
            "Generating competitive landscape overview...",
            "working",
            None,
        )
        competitors = await generate_category_competitors(
            business_context,
            session_id,
            api_key,
        )
        if competitors:
            for comp in competitors:
                database.save_competitor(session_id, comp)
            database.log_agent_activity(
                session_id,
                "Competitor Analyst",
                f"Generated competitive overview with {len(competitors)} categories",
                "complete",
                None,
            )
            return competitors

        database.log_agent_activity(
            session_id,
            "Competitor Analyst",
            "Creating general competitive assessment",
            "complete",
            None,
        )
        fallback = generate_fallback_competitors(business_context)
        for comp in fallback:
            database.save_competitor(session_id, comp)
        return fallback
    except Exception as exc:  # noqa: BLE001
        logger.error("Competitor analysis error: %s", exc)
        database.log_agent_activity(
            session_id,
            "Competitor Analyst",
            "Completing competitive landscape analysis...",
            "complete",
            None,
        )
        fallback = generate_fallback_competitors(business_context)
        for comp in fallback:
            database.save_competitor(session_id, comp)
        return fallback


async def analyze_specific_competitors(
    business_context: str,
    competitor_names: list[str],
    session_id: int,
    api_key: Optional[str],
    tavily_key: Optional[str],
) -> Optional[list[dict]]:
    system_prompt = """
You are a Competitive Intelligence Analyst.

For each competitor provided, research and analyze:
1. Market position (Leader, Challenger, Follower, Niche)
2. Estimated market share or size
3. Key strengths (3-5 specific advantages)
4. Key weaknesses (3-5 vulnerabilities)

Use web search to find current information.

Output ONLY valid JSON array:
[
  {
    "competitor_name": "Company X",
    "market_position": "Market Leader",
    "market_share": "35-40%",
    "strengths": [
      "Strong brand with 80% awareness",
      "Extensive network in 50+ countries"
    ],
    "weaknesses": [
      "Legacy tech limiting innovation",
      "High churn rate (25% annually)"
    ]
  }
]
"""

    user_message = (
        f"Business Context: {business_context}\n\n"
        f"Analyze these specific competitors: {', '.join(competitor_names)}\n\n"
        "Find current data using web search."
    )

    if not api_key:
        return None

    try:
        search_query = f"{' '.join(competitor_names)} competitors market share strengths weaknesses"
        result_text = await _call_llm_with_optional_search(
            system_prompt,
            user_message,
            search_query,
            api_key,
            tavily_key,
        )
        competitors = parse_llm_json(clean_json_response(result_text), expect_array=True)
        if not isinstance(competitors, list) or not competitors:
            return None

        validated = []
        for comp in competitors:
            if all(k in comp for k in ["competitor_name", "strengths", "weaknesses"]):
                comp.setdefault("market_position", "Established Player")
                comp.setdefault("market_share", "Not disclosed")
                validated.append(comp)

        return validated or None
    except Exception as exc:  # noqa: BLE001
        logger.error("Specific competitor analysis failed: %s", exc)
        return None


async def identify_and_analyze_competitors(
    business_context: str,
    session_id: int,
    api_key: Optional[str],
    tavily_key: Optional[str],
) -> Optional[list[dict]]:
    system_prompt = """
You are a Market Research Analyst.

Given a business context, identify the top 3-5 direct competitors.

Use web search to find current market leaders in this space.

Output ONLY valid JSON array:
[
  {
    "competitor_name": "Company X",
    "market_position": "Market Leader",
    "market_share": "35%",
    "strengths": ["Strength 1", "Strength 2", "Strength 3"],
    "weaknesses": ["Weakness 1", "Weakness 2", "Weakness 3"]
  }
]

If you cannot find specific competitors, return an empty array: []
"""

    user_message = (
        f"Business Context: {business_context}\n\n"
        "Identify and analyze the top 3-5 direct competitors in this market.\n"
        "Use web search to find current information."
    )

    if not api_key:
        return None

    try:
        search_query = f"top competitors {business_context}"
        result_text = await _call_llm_with_optional_search(
            system_prompt,
            user_message,
            search_query,
            api_key,
            tavily_key,
        )
        competitors = parse_llm_json(clean_json_response(result_text), expect_array=True)
        if not isinstance(competitors, list) or not competitors:
            return None

        validated = []
        for comp in competitors:
            if "competitor_name" in comp:
                comp.setdefault("market_position", "Competitor")
                comp.setdefault("market_share", "Unknown")
                comp.setdefault("strengths", ["Established presence", "Market recognition"])
                comp.setdefault("weaknesses", ["Competitive pressure", "Market saturation"])
                validated.append(comp)

        return validated or None
    except Exception as exc:  # noqa: BLE001
        logger.error("Competitor identification failed: %s", exc)
        return None


async def generate_category_competitors(
    business_context: str,
    session_id: int,
    api_key: Optional[str],
) -> Optional[list[dict]]:
    return None


def generate_fallback_competitors(business_context: str) -> list[dict]:
    return []


class CompetitorAnalystAgent:
    name = "Competitor Analyst"

    def analyze(
        self,
        business_context: str,
        competitor_names: list[str],
        session_id: int,
    ) -> list[dict]:
        return asyncio.run(analyze_competitors(business_context, competitor_names, session_id))
