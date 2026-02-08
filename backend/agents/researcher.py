from __future__ import annotations

import asyncio
import json
import os
from ..utils.parse_llm_json import parse_llm_json
from typing import Any, Optional

import httpx

from .. import database
from ..utils.error_handler import graceful_failure
from ..utils.json_parser import clean_json_response
from ..utils.source_validator import SourceValidator
from ..utils.tavily_search import tavily_search_filtered

SYSTEM_PROMPT = (
    "You are a Research Specialist AI with strict source quality standards.\n\n"
    "CRITICAL SOURCE REQUIREMENTS:\n"
    "- ONLY cite sources from: research papers, industry reports, government data, reputable news\n"
    "- NEVER cite: forums (Reddit, Quora), social media, game sites, download sites, entertainment\n"
    "- Each claim MUST have a specific, credible source\n"
    "- If you cannot find quality sources, explicitly state \"Limited credible data available\"\n\n"
    "Prioritize:\n"
    "1. Academic research and peer-reviewed papers\n"
    "2. Industry analysis reports (Gartner, McKinsey, etc.)\n"
    "3. Government statistics and official data\n"
    "4. Reputable business news (WSJ, Bloomberg, Reuters)\n"
    "5. Company financial reports and SEC filings\n\n"
    "Output JSON:\n"
    "{\n"
    "  \"findings\": \"Clear summary with specific data points\",\n"
    "  \"sources\": [\"url1\", \"url2\", \"url3\"],\n"
    "  \"source_map\": {\n"
    "    \"Specific claim with data\": \"source_url\"\n"
    "  },\n"
    "  \"confidence\": 0.85,\n"
    "  \"data_quality\": \"HIGH|MEDIUM|LOW\",\n"
    "  \"limitations\": \"Any gaps in available data\"\n"
    "}"
)

TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")
SCRAPEGRAPH_BASE_URL = os.getenv("SCRAPEGRAPH_BASE_URL", "https://api.scrapegraphai.com")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
RESEARCHER_MODEL = os.getenv("RESEARCHER_MODEL", "z-ai/glm-4.5-air:free")
TRUSTED_SEARCH_DOMAINS = [
    "statista",
    "mckinsey",
    "forbes",
    "reuters",
    "bloomberg",
    "techcrunch",
    "gov",
]

BAD_DOMAINS = [
    "reddit.com",
    "tiktok.com",
    "apk",
    "wordle",
    "game",
    "download",
    "entertainment",
    "forum",
]


def filter_sources(urls: list[str]) -> list[str]:
    cleaned = []
    for url in urls:
        if not any(bad in url.lower() for bad in BAD_DOMAINS):
            cleaned.append(url)
    return cleaned[:8]


def _default_response(task: dict) -> dict:
    return {
        "task_id": int(task.get("task_id", 0)),
        "findings": f"No web results available yet for: {task.get('description', '')}",
        "sources": [],
        "source_map": {},
        "confidence": 0.3,
        "key_data_points": [],
        "data_quality": "LOW",
        "limitations": "Limited credible data available",
        "validated_sources": [],
    }


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text.strip()


def _extract_text_from_response(payload: dict[str, Any]) -> str:
    if "content" in payload and isinstance(payload["content"], list):
        for part in payload["content"]:
            if isinstance(part, dict) and part.get("type") == "text":
                return str(part.get("text", ""))
    if "choices" in payload and payload["choices"]:
        message = payload["choices"][0].get("message", {})
        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("text"):
                    return str(part["text"])
        if isinstance(content, str):
            return content
    if "text" in payload:
        return str(payload["text"])
    return ""


async def _call_tavily(
    task_description: str,
    api_key: str,
    *,
    max_results: int,
    search_depth: str,
) -> dict[str, Any]:
    results = await tavily_search_filtered(
        task_description,
        api_key,
        max_results=max_results,
        search_depth=search_depth,
    )
    return {"results": results}


async def _call_scrapegraph(task_description: str, api_key: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "prompt": f"Research this task: {task_description}",
        "max_tokens": 4000,
    }
    async with httpx.AsyncClient(timeout=40) as client:
        response = await client.post(f"{SCRAPEGRAPH_BASE_URL}/v1/chat", headers=headers, json=body)
        response.raise_for_status()
        return response.json()


async def _call_openrouter_general(
    system_prompt: str,
    user_message: str,
    api_key: str,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": RESEARCHER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 1400,
        "temperature": 0.3,
    }
    timeout_seconds = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "20"))
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(OPENROUTER_URL, headers=headers, json=body)
        response.raise_for_status()
        return response.json()


def _count_trusted_results(results: list[dict[str, Any]]) -> int:
    count = 0
    for result in results:
        url = str(result.get("url", "")).lower()
        if any(domain in url for domain in TRUSTED_SEARCH_DOMAINS):
            count += 1
    return count


def _build_refined_query(task_description: str) -> str:
    return (
        f"{task_description} site:statista.com OR site:mckinsey.com OR "
        "site:techcrunch.com OR site:reuters.com OR site:bloomberg.com OR "
        "site:forbes.com OR site:gov"
    )


async def _research_from_general_knowledge(
    system_prompt: str,
    task_description: str,
    api_key: str,
) -> dict:
    payload = await _call_openrouter_general(
        system_prompt,
        f"Research this task without web search: {task_description}",
        api_key,
    )
    content = _extract_text_from_response(payload)
    cleaned = clean_json_response(content)
    return parse_llm_json(cleaned)


@graceful_failure("Gathering additional research...")
async def research_task(
    task: dict,
    task_id: int,
    session_id: int,
    attempt: int = 1,
    critic_feedback: Optional[list[str]] = None,
    max_results_override: Optional[int] = None,
) -> dict:
    database.log_agent_activity(
        session_id,
        "Researcher",
        f"Researching task {task.get('task_number')}...",
        "working",
        None,
    )

    task_description = task.get("description", "")
    system_prompt = SYSTEM_PROMPT
    if attempt > 1:
        issues = critic_feedback or task.get("critic_issues") or task.get("critic_feedback")
        if issues:
            system_prompt += (
                "\nPrevious attempt was rejected because: "
                f"{issues}. Address these concerns."
            )

    api_key = os.getenv("TAVILY_API_KEY")
    scrape_key = os.getenv("SCRAPEGRAPH_API_KEY")

    last_error: Optional[str] = None
    payload: Optional[dict[str, Any]] = None

    if api_key:
        words = [w for w in (task_description or "").split() if w]
        is_large = len(words) >= 18 or len(task_description or "") >= 140
        max_small = int(os.getenv("TAVILY_MAX_RESULTS_SMALL", "3"))
        max_large = int(os.getenv("TAVILY_MAX_RESULTS_LARGE", "5"))
        max_results = max_small if not is_large else max_large
        if max_results_override is not None:
            max_results = max_results_override
        max_results = max(2, min(20, max_results))
        search_depth = os.getenv("TAVILY_SEARCH_DEPTH", "advanced")
        for retry in range(2):
            try:
                payload = await _call_tavily(
                    task_description,
                    api_key,
                    max_results=max_results,
                    search_depth=search_depth,
                )
                break
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if retry == 0:
                    await asyncio.sleep(0.5)
                    continue

    if payload is None and scrape_key:
        try:
            payload = await _call_scrapegraph(task_description, scrape_key)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

    if payload is None:
        database.log_agent_activity(
            session_id,
            "Researcher",
            "Research service unavailable. Using fallback results.",
            "rejected",
            None,
        )
        result = _default_response({"task_id": task_id, **task})
        database.save_research_findings(
            task_id,
            result["findings"],
            result["sources"],
            result["confidence"],
            result["source_map"],
            attempt,
            None,
        )
        database.log_agent_activity(
            session_id,
            "Researcher",
            f"Completed task {task.get('task_number')}",
            "complete",
            None,
        )
        return result

    used_general_knowledge = False

    if "results" in payload and isinstance(payload.get("results"), list):
        results = payload.get("results", [])
        if not results:
            database.log_agent_activity(
                session_id,
                "Researcher",
                "⚠️ No quality sources found - using general knowledge",
                "warning",
                None,
            )
            if os.getenv("OPEN_ROUTER_API_KEY"):
                try:
                    parsed = await _research_from_general_knowledge(
                        system_prompt,
                        task_description,
                        os.getenv("OPEN_ROUTER_API_KEY"),
                    )
                    findings = str(parsed.get("findings", ""))
                    sources = (
                        parsed.get("sources", [])
                        if isinstance(parsed.get("sources", []), list)
                        else []
                    )
                    confidence = float(parsed.get("confidence", 0.5))
                    key_data_points = (
                        parsed.get("key_data_points", [])
                        if isinstance(parsed.get("key_data_points", []), list)
                        else []
                    )
                    source_map = (
                        parsed.get("source_map", {})
                        if isinstance(parsed.get("source_map", {}), dict)
                        else {}
                    )
                    used_general_knowledge = True
                except Exception:  # noqa: BLE001
                    result = _default_response({"task_id": task_id, **task})
                    database.save_research_findings(
                        task_id,
                        result["findings"],
                        result["sources"],
                        result["confidence"],
                        result["source_map"],
                        attempt,
                        None,
                    )
                    database.log_agent_activity(
                        session_id,
                        "Researcher",
                        f"Completed task {task.get('task_number')}",
                        "complete",
                        None,
                    )
                    return result
            else:
                result = _default_response({"task_id": task_id, **task})
                database.save_research_findings(
                    task_id,
                    result["findings"],
                    result["sources"],
                    result["confidence"],
                    result["source_map"],
                    attempt,
                    None,
                )
                database.log_agent_activity(
                    session_id,
                    "Researcher",
                    f"Completed task {task.get('task_number')}",
                    "complete",
                    None,
                )
                return result
        else:
            trusted_count = _count_trusted_results(results)
            if trusted_count == 0:
                database.log_agent_activity(
                    session_id,
                    "Researcher",
                    "⚠️ Search returned low-quality sources - refining search",
                    "warning",
                    None,
                )
                refined_query = _build_refined_query(task_description)
                refined_payload = await _call_tavily(
                    refined_query,
                    api_key,
                    max_results=max_results,
                    search_depth=search_depth,
                )
                results = refined_payload.get("results", []) if refined_payload else []
                if not results:
                    database.log_agent_activity(
                        session_id,
                        "Researcher",
                        "⚠️ Refined search returned low-quality sources - using general knowledge",
                        "warning",
                        None,
                    )
                    if os.getenv("OPEN_ROUTER_API_KEY"):
                        try:
                            parsed = await _research_from_general_knowledge(
                                system_prompt,
                                task_description,
                                os.getenv("OPEN_ROUTER_API_KEY"),
                            )
                            findings = str(parsed.get("findings", ""))
                            sources = (
                                parsed.get("sources", [])
                                if isinstance(parsed.get("sources", []), list)
                                else []
                            )
                            confidence = float(parsed.get("confidence", 0.5))
                            key_data_points = (
                                parsed.get("key_data_points", [])
                                if isinstance(parsed.get("key_data_points", []), list)
                                else []
                            )
                            source_map = (
                                parsed.get("source_map", {})
                                if isinstance(parsed.get("source_map", {}), dict)
                                else {}
                            )
                            used_general_knowledge = True
                        except Exception:  # noqa: BLE001
                            result = _default_response({"task_id": task_id, **task})
                            database.save_research_findings(
                                task_id,
                                result["findings"],
                                result["sources"],
                                result["confidence"],
                                result["source_map"],
                                attempt,
                                None,
                            )
                            database.log_agent_activity(
                                session_id,
                                "Researcher",
                                f"Completed task {task.get('task_number')}",
                                "complete",
                                None,
                            )
                            return result
        if not used_general_knowledge:
            sources = [item.get("url") for item in results if item.get("url")]
            snippets = [item.get("content") for item in results if item.get("content")]
            findings = " ".join(snippets[:3]).strip()
            key_data_points = [snippet for snippet in snippets[:3] if snippet]
            confidence = 0.7 if len(sources) >= 3 else 0.5
            source_map = {}
    else:
        content = _extract_text_from_response(payload)
        content = _strip_code_fences(content)
        try:
            parsed = parse_llm_json(content)
            findings = str(parsed.get("findings", ""))
            sources = (
                parsed.get("sources", []) if isinstance(parsed.get("sources"), list) else []
            )
            confidence = float(parsed.get("confidence", 0.5))
            key_data_points = (
                parsed.get("key_data_points", [])
                if isinstance(parsed.get("key_data_points"), list)
                else []
            )
            source_map = (
                parsed.get("source_map", {}) if isinstance(parsed.get("source_map"), dict) else {}
            )
        except (ValueError, TypeError, KeyError) as exc:
            database.log_agent_activity(
                session_id,
                "Researcher",
                "Research response format issue. Using fallback results.",
                "rejected",
                None,
            )
            result = _default_response({"task_id": task_id, **task})
            database.save_research_findings(
                task_id,
                result["findings"],
                result["sources"],
                result["confidence"],
                result["source_map"],
                attempt,
                None,
            )
            database.log_agent_activity(
                session_id,
                "Researcher",
                f"Completed task {task.get('task_number')}",
                "complete",
                None,
            )
            return result

    sources = filter_sources([str(item) for item in sources])
    result = {
        "task_id": task_id,
        "findings": findings,
        "sources": sources,
        "source_map": source_map,
        "confidence": confidence,
        "key_data_points": [str(item) for item in key_data_points],
    }

    raw_sources = result.get("sources", [])
    database.log_agent_activity(
        session_id,
        "Researcher",
        f"Validating {len(raw_sources)} sources for quality...",
        "working",
        None,
    )

    validated_sources = SourceValidator.filter_sources(raw_sources, min_quality="MEDIUM")
    if not validated_sources:
        database.log_agent_activity(
            session_id,
            "Researcher",
            "⚠️ WARNING: No credible sources found for this task",
            "warning",
            None,
        )
        result["confidence"] = max(0.3, float(result.get("confidence", 0.5)) * 0.5)
        result["data_quality"] = "LOW"
        result["limitations"] = "Limited credible sources available"
        result["sources"] = []
        result["validated_sources"] = []
    else:
        avg_source_confidence = sum(s["confidence"] for s in validated_sources) / len(
            validated_sources
        )
        result["confidence"] = float(result.get("confidence", 0.7)) * avg_source_confidence
        high_quality_pct = sum(1 for s in validated_sources if s["quality"] == "HIGH") / len(
            validated_sources
        )
        if high_quality_pct >= 0.6:
            result["data_quality"] = "HIGH"
        elif high_quality_pct >= 0.3:
            result["data_quality"] = "MEDIUM"
        else:
            result["data_quality"] = "LOW"
        result["sources"] = [s["url"] for s in validated_sources]
        result["validated_sources"] = validated_sources
        quality_summary = SourceValidator.get_quality_summary(validated_sources)
        database.log_agent_activity(
            session_id,
            "Researcher",
            f"✓ {quality_summary}",
            "complete",
            None,
        )

    result.setdefault("limitations", None)

    database.save_research_findings(
        task_id,
        result["findings"],
        result["sources"],
        result["confidence"],
        result["source_map"],
        attempt,
        {
            "data_quality": result.get("data_quality"),
            "validated_sources": result.get("validated_sources", []),
            "limitations": result.get("limitations"),
        },
    )
    database.log_agent_activity(
        session_id,
        "Researcher",
        f"Completed task {task.get('task_number')}",
        "complete",
        None,
    )
    return result


class ResearcherAgent:
    name = "Researcher"

    def research(
        self,
        task: dict,
        task_id: int,
        session_id: int,
        attempt: int = 1,
        critic_feedback: Optional[list[str]] = None,
    ) -> dict:
        return asyncio.run(research_task(task, task_id, session_id, attempt, critic_feedback))
