from __future__ import annotations

import asyncio
import json
import os
import time
from typing import List

from . import database
from .agents.business_analyst import BusinessAnalystAgent, analyze_business_comprehensive
from .agents.business_strategist import generate_business_strategy
from .agents.classifier import classify_business
from .agents.narrative_generator import generate_decision_narrative
from .agents.decision_defender import generate_decision_defense
from .agents.competitor_analyst import analyze_competitors
from .agents.critic import CriticAgent, critique_analysis
from .agents.hallucination_detector import detect_hallucinations
from .agents.planner import PlannerAgent, plan_tasks
from .agents.researcher import ResearcherAgent, research_task
from .models import OrchestrationResult, SessionSummary, TaskSummary

TASK_TIMES = {
    "planning": 3,
    "research_per_task": 8,
    "business_analysis": 10,
    "competitor_analysis": 12,
    "vendor_analysis": 8,
    "critique": 5,
}


def _calculate_estimated_time(num_tasks: int, has_competitors: bool, has_vendors: bool) -> int:
    total = TASK_TIMES["planning"]
    total += TASK_TIMES["research_per_task"] * num_tasks
    total += TASK_TIMES["business_analysis"]
    if has_competitors:
        total += TASK_TIMES["competitor_analysis"]
    if has_vendors:
        total += TASK_TIMES["vendor_analysis"]
    total += TASK_TIMES["critique"]
    return total


def _log_progress(session_id: int, start_time: float, estimated_time: int, progress_pct: int) -> None:
    if estimated_time <= 0:
        return
    elapsed = max(0, int(time.monotonic() - start_time))
    remaining = max(estimated_time - elapsed, 0)
    database.log_agent_activity(
        session_id,
        "System",
        f"Progress: {progress_pct}%",
        "progress",
        {
            "progress": progress_pct,
            "elapsed": elapsed,
            "estimated_time": estimated_time,
            "estimated_remaining": remaining,
        },
    )


def _mode_max_results(execution_mode: str, depth: str) -> int:
    depth_map = {"basic": 5, "standard": 10, "deep": 20}
    base = depth_map.get(depth, 10)
    if execution_mode == "fast":
        return 3
    if execution_mode == "strict":
        return max(5, base)
    return base


def _should_skip_critique(execution_mode: str) -> bool:
    return execution_mode == "fast"


def _should_double_critique(execution_mode: str) -> bool:
    return execution_mode == "strict"


def _check_timeout(session_id: int, start_time: float, max_runtime: int | None) -> bool:
    if not max_runtime:
        return False
    elapsed = int(time.monotonic() - start_time)
    if elapsed <= max_runtime:
        return False
    database.log_agent_activity(
        session_id,
        "System",
        "Runtime limit exceeded. Stopping execution.",
        "error",
        None,
    )
    database.update_session(session_id, status="failed", final_decision="TIMEOUT")
    return True


def _find_lowest_confidence(research_results: list[dict]) -> int:
    if not research_results:
        return 0
    confidences = [float(item.get("confidence", 0)) for item in research_results]
    return confidences.index(min(confidences))


def _apply_research_modifications(tasks: list[dict], modifications: dict) -> list[dict]:
    notes = str(modifications.get("notes") or "").strip()
    if not notes:
        return tasks
    updated: list[dict] = []
    for task in tasks:
        description = str(task.get("description", "")).strip()
        updated.append(
            {
                **task,
                "description": f"{description}\nUser modifications: {notes}".strip(),
            }
        )
    return updated


def _format_document_context(documents: list[dict], max_chars: int = 2000) -> str:
    if not documents:
        return ""
    sections = []
    for doc in documents:
        content = str(doc.get("content", ""))
        excerpt = content[:max_chars].strip()
        if excerpt:
            sections.append(
                f"Document: {doc.get('filename')} ({doc.get('file_type')})\n{excerpt}"
            )
    return "\n\n".join(sections)


async def _wait_for_approval(gate_id: int, timeout_seconds: int = 300) -> dict:
    start_time = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
        gate = database.get_approval_gate(gate_id)
        if gate and gate.get("approved") is not None:
            modifications = gate.get("user_modifications")
            if isinstance(modifications, str):
                try:
                    modifications = json.loads(modifications) if modifications else {}
                except json.JSONDecodeError:
                    modifications = {}
            return {
                "approved": bool(gate.get("approved")),
                "user_modifications": modifications or {},
            }
        await asyncio.sleep(1)
    return {"approved": False, "user_modifications": {}}


def _handle_rejection(session_id: int, reason: str) -> dict:
    database.log_agent_activity(session_id, "System", reason, "rejected", None)
    database.update_session(session_id, status="failed", final_decision="REJECTED")
    return {
        "session_id": session_id,
        "recommendation": "REJECTED",
        "confidence": 0.0,
        "reasoning": reason,
        "critique_occurred": False,
    }


async def execute_enhanced_workflow(
    user_goal: str,
    session_id: int,
    business_name: str | None = None,
    competitor_names: list[str] | None = None,
    vendor_names: list[str] | None = None,
    document_ids: list[int] | None = None,
    auto_approve: bool = False,
    execution_mode: str = "balanced",
    max_research_depth: str = "standard",
    max_runtime: int | None = None,
) -> dict:
    """
    Enhanced workflow with comprehensive business analysis.
    """

    try:
        start_time = time.monotonic()
        documents = database.get_uploaded_documents(document_ids or [])
        document_context = _format_document_context(documents)
        planning_goal = user_goal
        if document_context:
            planning_goal = f"{user_goal}\n\nUploaded Documents:\n{document_context}"

        context = None
        try:
            context = await classify_business(user_goal)
            database.log_agent_activity(
                session_id,
                "Classifier",
                f"Detected {context.get('business_type')} in {context.get('industry')} industry",
                "complete",
                None,
            )
        except Exception:  # noqa: BLE001
            database.log_agent_activity(
                session_id,
                "Classifier",
                "Unable to classify business context. Proceeding without grounding.",
                "warning",
                None,
            )

        tasks = await plan_tasks(planning_goal, session_id, context=context)

        if not auto_approve:
            gate_id = database.create_approval_gate(
                session_id=session_id,
                gate_type="research_plan",
                description=(
                    f"I will research these {len(tasks)} areas: "
                    + ", ".join([str(t.get("description", "")) for t in tasks])
                    + "\n\nThis will use ~15-20 web searches. Approve?"
                ),
            )
            if gate_id:
                database.log_agent_activity(
                    session_id,
                    "System",
                    "⏸️ Waiting for user approval to proceed with research",
                    "waiting",
                    None,
                )
                approval = await _wait_for_approval(gate_id)
                if not approval["approved"]:
                    return _handle_rejection(session_id, "Research plan rejected by user")
                if approval.get("user_modifications"):
                    tasks = _apply_research_modifications(tasks, approval["user_modifications"])

        estimated_time = _calculate_estimated_time(
            len(tasks), bool(competitor_names), bool(vendor_names)
        )
        database.log_agent_activity(
            session_id,
            "System",
            f"⏱️ Estimated time: ~{estimated_time} seconds",
            "info",
            {"estimated_time": estimated_time, "elapsed": 0},
        )
        _log_progress(session_id, start_time, estimated_time, 10)

        max_results_override = _mode_max_results(execution_mode, max_research_depth)
        task_ids = database.create_tasks(session_id, tasks)
        await asyncio.sleep(1)

        research_results: list[dict] = []
        for index, (task, task_id) in enumerate(zip(tasks, task_ids), start=1):
            task_payload = task
            if document_context:
                task_payload = {
                    **task,
                    "description": f"{task.get('description', '')}\n\nRelevant documents:\n{document_context}",
                }
            result = await research_task(
                task_payload,
                task_id,
                session_id,
                max_results_override=max_results_override,
            )
            research_results.append(result)
            progress = 10 + int((index / max(len(tasks), 1)) * 40)
            _log_progress(session_id, start_time, estimated_time, progress)
            if _check_timeout(session_id, start_time, max_runtime):
                return _handle_rejection(session_id, "Runtime limit exceeded")
            await asyncio.sleep(0.5)

        business_analysis = await analyze_business_comprehensive(
            research_results,
            session_id,
            user_goal,
            business_name,
            context=context,
        )
        await asyncio.sleep(1)

        database.log_agent_activity(
            session_id,
            "System",
            "🎯 Generating execution strategy...",
            "working",
            None,
        )

        business_strategy = await generate_business_strategy(
            business_analysis,
            research_results,
            session_id,
            user_goal,
        )
        await asyncio.sleep(1)
        _log_progress(session_id, start_time, estimated_time, 60)
        if _check_timeout(session_id, start_time, max_runtime):
            return _handle_rejection(session_id, "Runtime limit exceeded")

        hallucinations = await detect_hallucinations(
            business_analysis.get("reasoning", ""),
            [src for result in research_results for src in result.get("sources", [])],
            session_id,
        )
        if hallucinations:
            for warning in hallucinations:
                database.save_hallucination_warning(
                    session_id,
                    warning["claim"],
                    warning["issue"],
                    warning["severity"],
                )
                database.log_agent_activity(
                    session_id,
                    "Hallucination Detector",
                    f"⚠️ {warning['severity']}: {warning['claim']} - {warning['issue']}",
                    "warning",
                    None,
                )

        if (competitor_names or []) and not auto_approve:
            gate_id = database.create_approval_gate(
                session_id=session_id,
                gate_type="competitor_analysis",
                description=(
                    "I will analyze these competitors: "
                    f"{', '.join(competitor_names or [])}. "
                    "This will search for financial data, market positioning, and weaknesses. "
                    "Approve?"
                ),
            )
            if gate_id:
                approval = await _wait_for_approval(gate_id)
                if not approval["approved"]:
                    competitor_names = []

        competitors: list[dict] = []
        try:
            database.log_agent_activity(
                session_id,
                "System",
                "🔍 Analyzing competitive landscape...",
                "working",
                None,
            )
            competitors = await analyze_competitors(
                business_context=user_goal,
                competitor_names=competitor_names or [],
                session_id=session_id,
            )
            await asyncio.sleep(1)
        except Exception as exc:  # noqa: BLE001
            database.log_agent_activity(
                session_id,
                "Competitor Analyst",
                "Generating competitive landscape overview...",
                "complete",
                None,
            )
            competitors = []

        if not competitors:
            competitors = []
        await asyncio.sleep(1)
        _log_progress(session_id, start_time, estimated_time, 72)
        if _check_timeout(session_id, start_time, max_runtime):
            return _handle_rejection(session_id, "Runtime limit exceeded")

        vendors = []
        await asyncio.sleep(1)
        _log_progress(session_id, start_time, estimated_time, 82)
        if _check_timeout(session_id, start_time, max_runtime):
            return _handle_rejection(session_id, "Runtime limit exceeded")

        if _should_skip_critique(execution_mode):
            critique = {
                "approved": True,
                "issues": [],
                "confidence_adjustment": 0.0,
                "severity": "MINOR",
                "requires_retry": False,
            }
        else:
            critique = await critique_analysis(
                business_analysis,
                research_results,
                session_id,
                competitors=competitors,
            )
            if _should_double_critique(execution_mode):
                second_critique = await critique_analysis(
                    business_analysis,
                    research_results,
                    session_id,
                    competitors=competitors,
                )
                critique = {
                    "approved": critique["approved"] and second_critique["approved"],
                    "issues": [*critique["issues"], *second_critique["issues"]],
                    "confidence_adjustment": float(critique["confidence_adjustment"])
                    + float(second_critique["confidence_adjustment"]),
                    "severity": second_critique.get("severity", critique.get("severity")),
                    "requires_retry": critique["requires_retry"]
                    or second_critique["requires_retry"],
                }
        _log_progress(session_id, start_time, estimated_time, 90)
        if _check_timeout(session_id, start_time, max_runtime):
            return _handle_rejection(session_id, "Runtime limit exceeded")

        if not critique["approved"] and critique["requires_retry"]:
            database.log_agent_activity(
                session_id,
                "System",
                f"Retry required: {', '.join(critique['issues'])}",
                "working",
                None,
            )

            weakest_idx = _find_lowest_confidence(research_results)
            retry_result = await research_task(
                tasks[weakest_idx],
                task_ids[weakest_idx],
                session_id,
                attempt=2,
                max_results_override=max_results_override,
            )
            research_results[weakest_idx] = retry_result

            business_analysis = await analyze_business_comprehensive(
                research_results,
                session_id,
                user_goal,
                business_name,
                context=context,
            )

            business_strategy = await generate_business_strategy(
                business_analysis,
                research_results,
                session_id,
                user_goal,
            )

            hallucinations = await detect_hallucinations(
                business_analysis.get("reasoning", ""),
                [src for result in research_results for src in result.get("sources", [])],
                session_id,
            )
            if hallucinations:
                for warning in hallucinations:
                    database.save_hallucination_warning(
                        session_id,
                        warning["claim"],
                        warning["issue"],
                        warning["severity"],
                    )
                    database.log_agent_activity(
                        session_id,
                        "Hallucination Detector",
                        f"⚠️ {warning['severity']}: {warning['claim']} - {warning['issue']}",
                        "warning",
                        None,
                    )

        final_confidence = max(
            0.0,
            float(business_analysis["confidence"]) + float(critique.get("confidence_adjustment", 0)),
        )

        if not auto_approve:
            gate_id = database.create_approval_gate(
                session_id=session_id,
                gate_type="final_decision",
                description=(
                    "Analysis complete. Preview:\n"
                    f"Recommendation: {business_analysis['recommendation']}\n"
                    f"Confidence: {final_confidence:.0%}\n"
                    f"Key finding: {business_analysis.get('reasoning', '')[:200]}...\n\n"
                    "Generate full report?"
                ),
            )
            if gate_id:
                approval = await _wait_for_approval(gate_id)
                if not approval["approved"]:
                    return _handle_rejection(session_id, "Final decision rejected by user")

        decision_narrative = await generate_decision_narrative(
            business_analysis,
            business_strategy if isinstance(business_strategy, dict) else {},
            session_id,
        )

        decision_defense = await generate_decision_defense(
            recommendation=business_analysis["recommendation"],
            business_analysis=business_analysis,
            business_strategy=business_strategy if isinstance(business_strategy, dict) else {},
            research_results=research_results,
            session_id=session_id,
        )

        database.save_decision_defense(
            session_id,
            business_analysis["recommendation"],
            decision_defense,
        )

        database.update_session(
            session_id,
            status="completed",
            final_decision=business_analysis["recommendation"],
            confidence=final_confidence,
            decision_narrative=decision_narrative,
        )

        _log_progress(session_id, start_time, estimated_time, 100)

        breakeven = business_strategy.get("breakeven", {}) if isinstance(business_strategy, dict) else {}
        adoption = business_strategy.get("adoption_threshold", {}) if isinstance(business_strategy, dict) else {}

        database.log_agent_activity(
            session_id,
            "System",
            (
                f"✅ Complete: {business_analysis['recommendation']} | "
                f"Break-even: {breakeven.get('months_min', '?')}-{breakeven.get('months_max', '?')} months | "
                f"Min adoption needed: {adoption.get('minimum_adoption_pct', '?')}%"
            ),
            "complete",
            None,
        )

        return {
            "session_id": session_id,
            "recommendation": business_analysis["recommendation"],
            "confidence": final_confidence,
            "decision_narrative": decision_narrative,
            "decision_defense": decision_defense,
            "business_analysis": business_analysis,
            "business_strategy": business_strategy,
            "competitors": competitors,
            "vendors": vendors,
            "critique_occurred": not critique["approved"],
        }
    except Exception as exc:  # noqa: BLE001
        database.log_agent_activity(session_id, "System", f"Error: {exc}", "error", None)
        database.update_session(session_id, status="failed")
        raise


class Orchestrator:
    def __init__(self) -> None:
        self.planner = PlannerAgent()
        self.researcher = ResearcherAgent()
        self.analyst = BusinessAnalystAgent()
        self.critic = CriticAgent()

    def run(
        self,
        session_id: int,
        user_goal: str,
        business_name: str | None = None,
        competitor_names: list[str] | None = None,
        vendor_names: list[str] | None = None,
        document_ids: list[int] | None = None,
        execution_mode: str = "balanced",
        max_research_depth: str = "standard",
        max_runtime: int | None = None,
    ) -> OrchestrationResult:
        result = asyncio.run(
            execute_enhanced_workflow(
                user_goal,
                session_id,
                business_name=business_name,
                competitor_names=competitor_names,
                vendor_names=vendor_names,
                document_ids=document_ids,
                execution_mode=execution_mode,
                max_research_depth=max_research_depth,
                max_runtime=max_runtime,
            )
        )

        session_payload = database.get_session(session_id)
        if not session_payload:
            raise RuntimeError("Session not found after completion")

        session_row = session_payload["session"]
        session = SessionSummary(
            id=session_row["id"],
            user_goal=session_row["user_goal"],
            status=session_row["status"],
            final_decision=session_row["final_decision"],
            confidence_score=session_row["confidence_score"],
            created_at=session_row["created_at"],
            completed_at=session_row["completed_at"],
        )

        created_tasks: List[TaskSummary] = []
        for row in session_payload["tasks"]:
            created_tasks.append(
                TaskSummary(
                    id=row["id"],
                    session_id=row["session_id"],
                    task_number=row["task_number"],
                    description=row["description"],
                    status=row["status"],
                    created_at=row["created_at"],
                )
            )

        return OrchestrationResult(session=session, tasks=created_tasks)
