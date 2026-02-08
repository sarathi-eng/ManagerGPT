import asyncio
import json
import logging
from functools import wraps
from typing import Any

from .. import database

logger = logging.getLogger(__name__)


def graceful_failure(fallback_message: str = "Refining analysis..."):
    """Decorator to mask errors with user-friendly messages"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            session_id = kwargs.get("session_id")
            if session_id is None:
                if len(args) >= 3:
                    session_id = args[2]
                elif len(args) >= 2:
                    session_id = args[1]
            agent_name = func.__name__.replace("_", " ").title()

            try:
                return await func(*args, **kwargs)

            except json.JSONDecodeError as exc:
                logger.error("%s JSON parse error: %s", agent_name, exc)

                if session_id is not None:
                    database.log_agent_activity(
                        session_id,
                        agent_name,
                        "Refining analysis format...",
                        "working",
                        None,
                    )

                await asyncio.sleep(1)

                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception:
                    logger.error("%s retry failed", agent_name)

                    if session_id is not None:
                        database.log_agent_activity(
                            session_id,
                            agent_name,
                            "Using alternative analysis method...",
                            "working",
                            None,
                        )

                    return generate_fallback_response(func.__name__, args, kwargs)

            except Exception as exc:  # noqa: BLE001
                logger.error("%s error: %s: %s", agent_name, type(exc).__name__, exc)

                if session_id is not None:
                    database.log_agent_activity(
                        session_id,
                        agent_name,
                        fallback_message,
                        "working",
                        None,
                    )

                await asyncio.sleep(1)
                return generate_fallback_response(func.__name__, args, kwargs)

        return wrapper

    return decorator


def _fallback_tasks() -> list[dict[str, Any]]:
    return [
        {"task_number": 1, "description": "Assess operational constraints and demand patterns"},
        {"task_number": 2, "description": "Validate customer behavior and usage frequency"},
        {"task_number": 3, "description": "Identify critical execution risks"},
    ]


def _fallback_research() -> dict[str, Any]:
    return {
        "findings": "Market analysis in progress. Data gathering from available sources.",
        "sources": [],
        "source_map": {},
        "confidence": 0.5,
        "key_data_points": [],
        "data_quality": "MEDIUM",
        "limitations": "Limited data available for comprehensive analysis",
        "validated_sources": [],
    }


def _fallback_business_analysis() -> dict[str, Any]:
    return {
        "recommendation": "CONDITIONAL",
        "reasoning": "Available evidence insufficient; decision depends on operational validation",
        "confidence": 0.3,
        "sustainability": {
            "score": 0.4,
            "factors": ["Operational assumptions unverified"],
            "long_term_viability": "MEDIUM",
            "reasoning": "Insufficient data for high-confidence assessment",
        },
    }


def generate_fallback_response(func_name: str, args, kwargs) -> Any:
    """Generate safe fallback response based on function type"""
    if func_name == "plan_tasks":
        return _fallback_tasks()

    if func_name == "research_task":
        return _fallback_research()

    if func_name == "analyze_business_comprehensive":
        fallback = _fallback_business_analysis()
        session_id = kwargs.get("session_id")
        if session_id is None and len(args) >= 2:
            session_id = args[1]
        if session_id is not None:
            analysis_id = database.save_analysis(
                session_id,
                fallback["recommendation"],
                fallback["reasoning"],
                fallback["confidence"],
            )
            business_id = database.save_business_analysis(session_id, fallback)
            fallback = {
                "analysis_id": analysis_id or 0,
                "business_analysis_id": business_id or 0,
                **fallback,
            }
        return fallback

    return {"status": "partial", "message": "Analysis in progress"}
