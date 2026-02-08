from __future__ import annotations

import asyncio
import json
import os
from typing import Any, List

import httpx

from .. import database
from ..utils.parse_llm_json import parse_llm_json
from ..utils.error_handler import graceful_failure
from ..models import TaskCreate

def _build_system_prompt(context: dict) -> str:
    business_type = context.get("business_type", "unknown")
    industry = context.get("industry", "unknown")
    target_customer = context.get("target_customer", "unknown")
    return (
        "You are a Strategic Planner AI.\n\n"
        "Business Context:\n"
        f"Type: {business_type}\n"
        f"Industry: {industry}\n"
        f"Target Customer: {target_customer}\n\n"
        "Create exactly 3 research tasks relevant to THIS industry.\n"
        "Avoid generic startup research.\n\n"
        "Output ONLY valid JSON:\n"
        "{\n  \"tasks\": [\n    {\"task_number\": 1, \"description\": \"...\"}\n  ]\n}"
    )

PRIMARY_MODEL = "arcee-ai/trinity-large-preview:free"
FALLBACK_MODEL = "arcee-ai/trinity-mini:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 512
TEMPERATURE = 0.7


def _default_tasks(user_goal: str, task_count: int) -> list[dict[str, Any]]:
    templates = [
        f"Research market size and growth trends related to: {user_goal}",
        "Analyze competitors (top 3-5) and differentiation",
        "Identify key risks, regulatory constraints, and privacy concerns",
        "Estimate pricing, willingness-to-pay, and unit economics assumptions",
        "Define target customer segments and key use cases",
        "Outline a go-to-market plan and distribution channels",
    ]
    task_count = max(3, min(int(task_count), len(templates)))
    return [
        {"task_number": idx, "description": templates[idx - 1]}
        for idx in range(1, task_count + 1)
    ]


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
    if "content" in payload and isinstance(payload["content"], list):
        first = payload["content"][0]
        if isinstance(first, dict) and first.get("text"):
            return str(first["text"])
    return ""


async def _call_openrouter(user_goal: str, model: str, api_key: str, context: dict) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": _build_system_prompt(context)},
            {"role": "user", "content": user_goal},
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
    }
    timeout_seconds = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "20"))
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(OPENROUTER_URL, headers=headers, json=body)
        response.raise_for_status()
        return response.json()


@graceful_failure("Refining task breakdown...")
async def plan_tasks(
    user_goal: str,
    session_id: int,
    context: dict,
) -> list[dict[str, Any]]:
    desired_count = 3
    database.log_agent_activity(
        session_id,
        "Planner",
        "Breaking down goal into tasks...",
        "working",
        None,
    )

    api_key = os.getenv("OPEN_ROUTER_API_KEY")
    if not api_key:
        database.log_agent_activity(
            session_id,
            "Planner",
            "Planner configuration missing; using default tasks",
            "rejected",
            None,
        )
        tasks = _default_tasks(user_goal, desired_count)
        database.create_tasks(session_id, tasks)
        database.log_agent_activity(session_id, "Planner", f"Created {len(tasks)} research tasks", "complete")
        return tasks

    models = [PRIMARY_MODEL, FALLBACK_MODEL]
    last_error: str | None = None


    for model in models:
        for attempt in range(2):
            try:
                payload = await _call_openrouter(user_goal, model, api_key, context)
                content = _extract_content(payload)
                data = parse_llm_json(content)
                tasks = data.get("tasks")
                if not isinstance(tasks, list) or len(tasks) != desired_count:
                    raise ValueError("Invalid tasks payload")

                normalized = []
                for idx, item in enumerate(tasks, start=1):
                    desc = item.get("description") if isinstance(item, dict) else None
                    normalized.append({"task_number": idx, "description": str(desc or "").strip()})
                database.create_tasks(session_id, normalized)
                database.log_agent_activity(
                    session_id,
                    "Planner",
                    f"Created {len(normalized)} research tasks",
                    "complete",
                )
                return normalized
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
                break

    database.log_agent_activity(
        session_id,
        "Planner",
        "Planner unavailable; using default tasks",
        "rejected",
        None,
    )
    tasks = _default_tasks(user_goal, desired_count)
    database.create_tasks(session_id, tasks)
    database.log_agent_activity(session_id, "Planner", f"Created {len(tasks)} research tasks", "complete")
    return tasks


class PlannerAgent:
    name = "Planner"

    def plan(self, user_goal: str, session_id: int, context: dict) -> List[TaskCreate]:
        tasks = asyncio.run(plan_tasks(user_goal, session_id, context))
        return [TaskCreate(**task) for task in tasks]
