from __future__ import annotations

import asyncio
import io
import json
import os
import secrets
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv
import pandas as pd
from PyPDF2 import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from . import database
from pydantic import BaseModel
from .orchestrator import Orchestrator

load_dotenv()
OPEN_ROUTER_API_KEY = os.getenv("OPEN_ROUTER_API_KEY")

app = FastAPI(title="ManagerGPT Backend")


# ── shared helpers ──────────────────────────────────────────────────

def _build_strategy(business_metrics: dict | None) -> dict | None:
    """Convert flat business_metrics row into nested strategy dict."""
    if not business_metrics:
        return None
    return {
        "breakeven": {
            "months_min": business_metrics.get("breakeven_months_min"),
            "months_max": business_metrics.get("breakeven_months_max"),
            "key_driver": business_metrics.get("breakeven_key_driver"),
            "assumptions": business_metrics.get("breakeven_assumptions", []),
        },
        "customer_segments": {
            "primary": {
                "segment": business_metrics.get("primary_segment"),
                "size": business_metrics.get("primary_segment_size"),
                "fit_score": 0,
                "reasoning": business_metrics.get("segment_reasoning"),
            },
            "secondary": {
                "segment": business_metrics.get("secondary_segment"),
                "size": "",
                "fit_score": 0,
                "reasoning": "",
            },
            "poor_fit": business_metrics.get("poor_fit_segments", []),
        },
        "pricing": {
            "optimal_min": business_metrics.get("optimal_price_min"),
            "optimal_max": business_metrics.get("optimal_price_max"),
            "sensitivity": business_metrics.get("pricing_sensitivity"),
            "price_points": business_metrics.get("price_points", {}),
            "reasoning": "",
        },
        "adoption_threshold": {
            "minimum_adoption_pct": business_metrics.get("minimum_adoption_pct"),
            "failure_threshold_pct": business_metrics.get("failure_threshold_pct"),
            "kpi": business_metrics.get("adoption_kpi_description"),
            "measurement_period_days": business_metrics.get("pivot_threshold_days") or 30,
            "reasoning": "",
        },
        "unit_economics": {
            "cost_per_unit": business_metrics.get("cost_per_unit"),
            "revenue_per_unit": business_metrics.get("revenue_per_unit"),
            "gross_margin_pct": business_metrics.get("gross_margin_pct"),
            "health": business_metrics.get("unit_economics_health"),
            "margin_buffer": business_metrics.get("margin_buffer"),
            "breakdown": {},
            "notes": "",
        },
        "launch_strategy": {
            "approach": business_metrics.get("launch_approach"),
            "steps": business_metrics.get("launch_steps", []),
            "total_timeline_days": business_metrics.get("timeline_days"),
            "reasoning": "",
        },
        "failure_signals": business_metrics.get("early_failure_signals", []),
        "comparable_cases": business_metrics.get("comparable_businesses", []),
        "pivot_suggestions": business_metrics.get("pivot_suggestions", []),
    }


def _build_report_response(
    session_payload: dict,
    decision_defense: Any = None,
    include_agent_activity: bool = False,
) -> dict[str, Any]:
    """Build the full report response dict used by get_session and view_shared_report."""
    session_row = session_payload["session"]
    analysis = session_payload.get("analysis", [])
    latest_analysis = analysis[-1] if analysis else None
    reasoning = latest_analysis.get("reasoning") if latest_analysis else None
    analysis_confidence = latest_analysis.get("confidence") if latest_analysis else None
    business_analysis = session_payload.get("business_analysis", [])
    latest_business = business_analysis[-1] if business_analysis else None
    business_confidence = latest_business.get("confidence") if latest_business else None

    pros = latest_business.get("pros", []) if latest_business else []
    cons = latest_business.get("cons", []) if latest_business else []
    sustainability = {
        "score": latest_business.get("sustainability_score", 0) if latest_business else 0,
        "factors": latest_business.get("sustainability_factors", []) if latest_business else [],
        "long_term_viability": latest_business.get("long_term_viability", "MEDIUM")
        if latest_business
        else "MEDIUM",
        "reasoning": latest_business.get("sustainability_reasoning")
        if latest_business and latest_business.get("sustainability_reasoning")
        else (reasoning or "No additional sustainability notes."),
    }
    investment = {
        "min": latest_business.get("initial_investment_min", 0) if latest_business else 0,
        "max": latest_business.get("initial_investment_max", 0) if latest_business else 0,
        "breakdown": latest_business.get("investment_breakdown", {}) if latest_business else {},
    }

    sources: list[str] = []
    source_map: dict[str, str] = {}
    for finding in session_payload.get("research", []):
        sources.extend([str(item) for item in finding.get("sources", [])])
        for claim, source in (finding.get("source_map") or {}).items():
            if claim and source and claim not in source_map:
                source_map[str(claim)] = str(source)
    deduped_sources: list[str] = []
    for item in sources:
        if item not in deduped_sources:
            deduped_sources.append(item)

    business_metrics = session_payload.get("business_metrics")
    strategy = _build_strategy(business_metrics)

    model_info = {
        "business_analyst_model": os.getenv("BUSINESS_ANALYST_MODEL", "z-ai/glm-4.5-air:free"),
        "competitor_analyst_model": os.getenv("COMPETITOR_ANALYST_MODEL", "z-ai/glm-4.5-air:free"),
        "vendor_analyst_model": os.getenv("VENDOR_ANALYST_MODEL", "z-ai/glm-4.5-air:free"),
        "openrouter_endpoint": "openrouter.ai",
    }
    if os.getenv("TAVILY_API_KEY"):
        research_provider = "tavily"
    elif os.getenv("SCRAPEGRAPH_API_KEY"):
        research_provider = "scrapegraph"
    else:
        research_provider = "none"
    research_info = {
        "provider": research_provider,
        "sources_count": len(deduped_sources),
    }

    result: dict[str, Any] = {
        "session_id": session_row["id"],
        "user_goal": session_row["user_goal"],
        "status": session_row["status"],
        "final_decision": session_row["final_decision"],
        "executive_summary": session_row.get("decision_narrative"),
        "decision_defense": decision_defense,
        "confidence_score": session_row["confidence_score"],
        "confidence": analysis_confidence or business_confidence,
        "reasoning": reasoning,
        "sources": deduped_sources,
        "source_map": source_map,
        "model_info": model_info,
        "research_info": research_info,
        "pros": pros,
        "cons": cons,
        "sustainability": sustainability,
        "investment": investment,
        "competitors": session_payload.get("competitors", []),
        "vendors": session_payload.get("vendors", []),
        "hallucination_warnings": session_payload.get("hallucination_warnings", []),
        "business_metrics": business_metrics,
        "strategy": strategy,
    }

    if include_agent_activity:
        agent_activity = []
        for row in session_payload.get("agent_logs", []):
            agent_activity.append(
                {
                    "agent": row.get("agent_name"),
                    "message": row.get("message"),
                    "status": row.get("status"),
                    "timestamp": row.get("created_at"),
                    "metadata": row.get("metadata"),
                }
            )
        result["agent_activity"] = agent_activity

    return result


class EnhancedGoalRequest(BaseModel):
    goal: str
    business_name: str | None = None
    competitor_names: list[str] = []
    vendor_names: list[str] = []
    document_ids: list[int] = []
    execution_mode: str = "balanced"
    max_research_depth: str = "standard"
    max_runtime: int | None = None


class ApprovalResponse(BaseModel):
    approved: bool
    modifications: dict | None = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    database.init_db()


def _run_orchestrator(
    session_id: int,
    goal: str,
    business_name: str | None = None,
    competitor_names: list[str] | None = None,
    vendor_names: list[str] | None = None,
    document_ids: list[int] | None = None,
    execution_mode: str = "balanced",
    max_research_depth: str = "standard",
    max_runtime: int | None = None,
) -> None:
    try:
        Orchestrator().run(
            session_id,
            goal,
            business_name=business_name,
            competitor_names=competitor_names,
            vendor_names=vendor_names,
            document_ids=document_ids,
            execution_mode=execution_mode,
            max_research_depth=max_research_depth,
            max_runtime=max_runtime,
        )
    except Exception as exc:  # noqa: BLE001 - surface error in logs
        print(f"Orchestrator failed for session {session_id}: {exc}")
        database.log_agent_activity(
            session_id,
            "System",
            f"Orchestration failed: {exc}",
            "error",
            None,
        )
        database.update_session(session_id, "failed", "FAILED", None)


@app.post("/api/execute")
async def execute_goal(
    payload: EnhancedGoalRequest, background_tasks: BackgroundTasks
) -> dict[str, int]:
    try:
        session_id = database.create_session(payload.goal)
        if session_id is None:
            raise RuntimeError("Failed to create session")
        database.log_agent_activity(
            session_id,
            "System",
            "Session created",
            "working",
            None,
        )
        background_tasks.add_task(
            _run_orchestrator,
            session_id,
            payload.goal,
            payload.business_name,
            payload.competitor_names,
            payload.vendor_names,
            payload.document_ids,
            payload.execution_mode,
            payload.max_research_depth,
            payload.max_runtime,
        )
        return {"session_id": session_id}
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to create session: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create session") from exc


@app.get("/api/stream/{session_id}")
async def stream_updates(session_id: int) -> EventSourceResponse:
    session_payload = database.get_session(session_id)
    if not session_payload:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        last_id = 0
        try:
            while True:
                logs = database.get_agent_logs(session_id, last_id)
                if not logs:
                    yield {"comment": "ping"}
                for row in logs:
                    last_id = row.get("id", last_id)
                    payload = {
                        "agent": row.get("agent_name"),
                        "message": row.get("message"),
                        "status": row.get("status") or "working",
                        "timestamp": row.get("created_at"),
                        "metadata": row.get("metadata"),
                    }
                    yield {"data": json.dumps(payload, ensure_ascii=False)}

                session_payload = database.get_session(session_id)
                if session_payload is None:
                    break
                if session_payload["session"]["status"] in ("completed", "failed"):
                    break
                await asyncio.sleep(0.5)
        except Exception as exc:  # noqa: BLE001
            print(f"Stream error for session {session_id}: {exc}")
            error_payload = {
                "agent": "System",
                "message": "Stream error",
                "status": "error",
                "timestamp": "",
            }
            yield {"data": json.dumps(error_payload, ensure_ascii=False)}

    return EventSourceResponse(event_generator())


@app.get("/api/session/{session_id}")
async def get_session(session_id: int) -> dict[str, Any]:
    try:
        session_payload = database.get_session(session_id)
        if not session_payload:
            raise HTTPException(status_code=404, detail="Session not found")
        decision_defense = database.get_decision_defense(session_id)
        return _build_report_response(session_payload, decision_defense, include_agent_activity=True)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to fetch session {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch session") from exc


@app.get("/api/sessions")
async def list_sessions() -> list[dict[str, Any]]:
    try:
        response: list[dict[str, Any]] = []
        for row in database.list_sessions():
            response.append(
                {
                    "session_id": row.get("id"),
                    "user_goal": row.get("user_goal"),
                    "status": row.get("status"),
                    "final_decision": row.get("final_decision"),
                    "confidence_score": row.get("confidence_score"),
                    "created_at": row.get("created_at"),
                    "completed_at": row.get("completed_at"),
                }
            )
        return response
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to list sessions: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list sessions") from exc


@app.post("/api/session/{session_id}/share")
async def create_share_link(session_id: int, request: Request) -> dict[str, str]:
    session_payload = database.get_session(session_id)
    if not session_payload:
        raise HTTPException(status_code=404, detail="Session not found")
    decision_defense = database.get_decision_defense(session_id)

    share_token = secrets.token_urlsafe(16)
    database.create_shared_report(session_id, share_token)
    base_url = str(request.base_url).rstrip("/")
    return {"share_url": f"{base_url}/report/{share_token}"}


@app.get("/report/{share_token}")
async def view_shared_report(share_token: str) -> dict[str, Any]:
    session_id = database.get_shared_report_session(share_token)
    if not session_id:
        raise HTTPException(status_code=404, detail="Report not found")

    session_payload = database.get_session(session_id)
    if not session_payload:
        raise HTTPException(status_code=404, detail="Session not found")

    decision_defense = database.get_decision_defense(session_id)
    return _build_report_response(session_payload, decision_defense)


@app.get("/api/session/{session_id}/export/pdf")
async def export_to_pdf(session_id: int) -> StreamingResponse:
    session_payload = database.get_session(session_id)
    if not session_payload:
        raise HTTPException(status_code=404, detail="Session not found")

    session_row = session_payload["session"]
    business_analysis = session_payload.get("business_analysis", [])
    latest_business = business_analysis[-1] if business_analysis else None
    pros = latest_business.get("pros", []) if latest_business else []
    cons = latest_business.get("cons", []) if latest_business else []

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Business Analysis Report", styles["Title"]))
    story.append(Paragraph(f"Session #{session_id}", styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))

    final_decision = session_row.get("final_decision") or "UNKNOWN"
    confidence = session_row.get("confidence_score") or 0

    story.append(Paragraph(f"<b>Recommendation:</b> {final_decision}", styles["Heading2"]))
    story.append(Paragraph(f"<b>Confidence:</b> {confidence:.0%}", styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Advantages:", styles["Heading3"]))
    for pro in pros[:5]:
        story.append(Paragraph(f"• {pro}", styles["Normal"]))

    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Challenges:", styles["Heading3"]))
    for con in cons[:5]:
        story.append(Paragraph(f"• {con}", styles["Normal"]))

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report_{session_id}.pdf"},
    )


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)) -> dict[str, Any]:
    content = await file.read()
    filename = file.filename or "upload"
    file_type = filename.split(".")[-1].lower() if "." in filename else ""

    try:
        if file_type == "pdf":
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join([(page.extract_text() or "") for page in reader.pages])
        elif file_type in {"xlsx", "xls"}:
            df = pd.read_excel(io.BytesIO(content))
            text = df.to_string(index=False)
        elif file_type == "csv":
            df = pd.read_csv(io.BytesIO(content))
            text = df.to_string(index=False)
        elif file_type == "txt":
            text = content.decode("utf-8", errors="ignore")
        else:
            raise ValueError("Unsupported file type")

        doc_id = database.save_uploaded_document(filename, file_type, text)
        if not doc_id:
            raise RuntimeError("Failed to save document")

        return {
            "document_id": doc_id,
            "filename": filename,
            "file_type": file_type,
            "content_preview": text[:500],
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@app.get("/api/approvals/{session_id}/pending")
async def get_pending_approvals(session_id: int) -> list[dict[str, Any]]:
    try:
        return database.get_pending_approvals(session_id)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to fetch approvals: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch approvals") from exc


@app.post("/api/approvals/{gate_id}/respond")
async def respond_to_approval_endpoint(gate_id: int, payload: ApprovalResponse) -> dict[str, str]:
    try:
        database.respond_to_approval(gate_id, payload.approved, payload.modifications)
        return {"status": "success"}
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to respond to approval: {exc}")
        raise HTTPException(status_code=500, detail="Failed to respond") from exc
