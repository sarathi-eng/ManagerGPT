from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "managerGPT.db")
SCHEMA_PATH = os.path.join(os.path.dirname(BASE_DIR), "schema.sql")


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
            schema_sql = handle.read()
        with get_db() as conn:
            conn.executescript(schema_sql)
            try:
                conn.execute("ALTER TABLE research_findings ADD COLUMN source_map TEXT")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE research_findings ADD COLUMN metadata TEXT")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE sessions ADD COLUMN decision_narrative TEXT")
            except Exception:
                pass
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS decision_defenses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER NOT NULL,
                        recommendation TEXT NOT NULL,
                        why_not_stop TEXT,
                        why_not_investigate TEXT,
                        why_not_proceed TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions(id)
                    )
                    """
                )
            except Exception:
                pass
    except Exception as exc:  # noqa: BLE001
        print(f"Database init error: {exc}")


def create_session(user_goal: str) -> Optional[int]:
    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sessions (user_goal, status, created_at)
                VALUES (?, 'running', ?)
                """,
                (user_goal, _now()),
            )
            return int(cursor.lastrowid)
    except Exception as exc:  # noqa: BLE001
        print(f"Create session error: {exc}")
        return None


def update_session(
    session_id: int,
    status: str,
    final_decision: Optional[str] = None,
    confidence: Optional[float] = None,
    decision_narrative: Optional[str] = None,
) -> None:
    try:
        completed_at = _now() if status in {"completed", "failed"} else None
        with get_db() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET status = ?,
                    final_decision = ?,
                    confidence_score = ?,
                    completed_at = ?,
                    decision_narrative = COALESCE(?, decision_narrative)
                WHERE id = ?
                """,
                (status, final_decision, confidence, completed_at, decision_narrative, session_id),
            )
    except Exception as exc:  # noqa: BLE001
        print(f"Update session error: {exc}")


_METRICS_JSON_FIELDS = [
    "breakeven_assumptions",
    "poor_fit_segments",
    "price_points",
    "launch_steps",
    "early_failure_signals",
    "comparable_businesses",
    "critical_skills",
    "pivot_suggestions",
]


def _parse_metrics_json_fields(metrics: dict) -> dict:
    """Parse JSON string fields in a business_metrics row."""
    for field in _METRICS_JSON_FIELDS:
        raw = metrics.get(field)
        if isinstance(raw, str):
            try:
                metrics[field] = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                metrics[field] = [] if field != "price_points" else {}
    return metrics


def get_session(session_id: int) -> Optional[dict]:
    try:
        with get_db() as conn:
            session_row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if not session_row:
                return None

            task_rows = conn.execute(
                "SELECT * FROM tasks WHERE session_id = ? ORDER BY task_number",
                (session_id,),
            ).fetchall()

            research_rows = conn.execute(
                """
                SELECT rf.*
                FROM research_findings rf
                JOIN tasks t ON rf.task_id = t.id
                WHERE t.session_id = ?
                ORDER BY rf.id
                """,
                (session_id,),
            ).fetchall()

            analysis_rows = conn.execute(
                "SELECT * FROM analysis_results WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()

            critique_rows = conn.execute(
                """
                SELECT c.*
                FROM critiques c
                JOIN analysis_results ar ON c.analysis_id = ar.id
                WHERE ar.session_id = ?
                ORDER BY c.id
                """,
                (session_id,),
            ).fetchall()

            log_rows = conn.execute(
                "SELECT * FROM agent_logs WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()

            hallucination_rows = conn.execute(
                "SELECT * FROM hallucination_warnings WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()

            business_rows = conn.execute(
                "SELECT * FROM business_analysis WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()

            competitor_rows = conn.execute(
                "SELECT * FROM competitors WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()

            vendor_rows = conn.execute(
                "SELECT * FROM vendors WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()

            metrics_row = conn.execute(
                """
                SELECT * FROM business_metrics
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()

        return {
            "session": dict(session_row),
            "tasks": [dict(row) for row in task_rows],
            "research": [
                {
                    **dict(row),
                    "sources": json.loads(row["sources"]) if row["sources"] else [],
                    "source_map": json.loads(row["source_map"]) if row["source_map"] else {},
                }
                for row in research_rows
            ],
            "analysis": [dict(row) for row in analysis_rows],
            "critiques": [
                {
                    **dict(row),
                    "issues": json.loads(row["issues"]) if row["issues"] else [],
                }
                for row in critique_rows
            ],
            "agent_logs": [
                {
                    **dict(row),
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
                }
                for row in log_rows
            ],
            "hallucination_warnings": [dict(row) for row in hallucination_rows],
            "business_analysis": [
                {
                    **dict(row),
                    "customer_pain_points": json.loads(row["customer_pain_points"])
                    if row["customer_pain_points"]
                    else [],
                    "pros": json.loads(row["pros"]) if row["pros"] else [],
                    "cons": json.loads(row["cons"]) if row["cons"] else [],
                    "sustainability_factors": json.loads(row["sustainability_factors"])
                    if row["sustainability_factors"]
                    else [],
                    "investment_breakdown": json.loads(row["investment_breakdown"])
                    if row["investment_breakdown"]
                    else None,
                }
                for row in business_rows
            ],
            "competitors": [
                {
                    **dict(row),
                    "strengths": json.loads(row["strengths"]) if row["strengths"] else [],
                    "weaknesses": json.loads(row["weaknesses"]) if row["weaknesses"] else [],
                }
                for row in competitor_rows
            ],
            "vendors": [
                {
                    **dict(row),
                    "advantages": json.loads(row["advantages"]) if row["advantages"] else [],
                    "disadvantages": json.loads(row["disadvantages"]) if row["disadvantages"] else [],
                    "alternatives_available": bool(row["alternatives_available"])
                    if row["alternatives_available"] is not None
                    else None,
                }
                for row in vendor_rows
            ],
            "business_metrics": _parse_metrics_json_fields(dict(metrics_row)) if metrics_row else None,
        }
    except Exception as exc:  # noqa: BLE001
        print(f"Get session error: {exc}")
        return None


def create_tasks(session_id: int, tasks: list) -> list[int]:
    task_ids: list[int] = []
    try:
        with get_db() as conn:
            existing = conn.execute(
                "SELECT id, task_number FROM tasks WHERE session_id = ? ORDER BY task_number",
                (session_id,),
            ).fetchall()
            if existing:
                return [row["id"] for row in existing]
            for task in tasks:
                cursor = conn.execute(
                    """
                    INSERT INTO tasks (session_id, task_number, description, status, created_at)
                    VALUES (?, ?, ?, 'pending', ?)
                    """,
                    (
                        session_id,
                        task.task_number if hasattr(task, "task_number") else task["task_number"],
                        task.description if hasattr(task, "description") else task["description"],
                        _now(),
                    ),
                )
                task_ids.append(int(cursor.lastrowid))
        return task_ids
    except Exception as exc:  # noqa: BLE001
        print(f"Create tasks error: {exc}")
        return []


def update_task_status(task_id: int, status: str) -> None:
    try:
        with get_db() as conn:
            conn.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (status, task_id),
            )
    except Exception as exc:  # noqa: BLE001
        print(f"Update task status error: {exc}")


def save_research_findings(
    task_id: int,
    findings: str,
    sources: list,
    confidence: Optional[float],
    source_map: Optional[dict] = None,
    attempt: int = 1,
    metadata: Optional[dict] = None,
) -> Optional[int]:
    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO research_findings (
                    task_id, findings, sources, source_map, confidence, attempt_number, metadata, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    findings,
                    json.dumps(sources or []),
                    json.dumps(source_map or {}),
                    confidence,
                    attempt,
                    json.dumps(metadata) if metadata else None,
                    _now(),
                ),
            )
            return int(cursor.lastrowid)
    except Exception as exc:  # noqa: BLE001
        print(f"Save research error: {exc}")
        return None


def get_all_research_for_session(session_id: int) -> list[dict]:
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT rf.*
                FROM research_findings rf
                JOIN tasks t ON rf.task_id = t.id
                WHERE t.session_id = ?
                ORDER BY rf.id
                """,
                (session_id,),
            ).fetchall()
        return [
            {
                **dict(row),
                "sources": json.loads(row["sources"]) if row["sources"] else [],
                "source_map": json.loads(row["source_map"]) if row["source_map"] else {},
            }
            for row in rows
        ]
    except Exception as exc:  # noqa: BLE001
        print(f"Get research error: {exc}")
        return []


def save_analysis(
    session_id: int,
    recommendation: str,
    reasoning: str,
    confidence: Optional[float],
) -> Optional[int]:
    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analysis_results (session_id, recommendation, reasoning, confidence, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, recommendation, reasoning, confidence, _now()),
            )
            return int(cursor.lastrowid)
    except Exception as exc:  # noqa: BLE001
        print(f"Save analysis error: {exc}")
        return None


def save_business_analysis(session_id: int, analysis: dict) -> Optional[int]:
    try:
        classification = analysis.get("business_classification", {}) or {}
        sustainability = analysis.get("sustainability", {}) or {}
        investment = analysis.get("investment", {}) or {}
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO business_analysis (
                    session_id,
                    business_type,
                    business_model,
                    target_customer,
                    customer_pain_points,
                    pros,
                    cons,
                    sustainability_score,
                    sustainability_factors,
                    long_term_viability,
                    initial_investment_min,
                    initial_investment_max,
                    investment_breakdown,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    classification.get("business_type"),
                    classification.get("business_model"),
                    classification.get("target_customer"),
                    json.dumps(classification.get("customer_pain_points", []) or []),
                    json.dumps(analysis.get("pros", []) or []),
                    json.dumps(analysis.get("cons", []) or []),
                    sustainability.get("score"),
                    json.dumps(sustainability.get("factors", []) or []),
                    sustainability.get("long_term_viability"),
                    investment.get("min"),
                    investment.get("max"),
                    json.dumps(investment.get("breakdown", {}) or {}),
                    _now(),
                ),
            )
            return int(cursor.lastrowid)
    except Exception as exc:  # noqa: BLE001
        print(f"Save business analysis error: {exc}")
        return None


def save_competitor(session_id: int, competitor: dict) -> Optional[int]:
    try:
        strengths = competitor.get("strengths", []) or []
        weaknesses = competitor.get("weaknesses", []) or []
        advantage = competitor.get("competitive_advantage")
        disadvantage = competitor.get("competitive_disadvantage")
        if advantage:
            strengths = [*strengths, f"Competitive advantage: {advantage}"]
        if disadvantage:
            weaknesses = [*weaknesses, f"Competitive disadvantage: {disadvantage}"]

        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO competitors (
                    session_id,
                    competitor_name,
                    market_position,
                    market_share,
                    strengths,
                    weaknesses,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    competitor.get("competitor_name"),
                    competitor.get("market_position"),
                    competitor.get("market_share"),
                    json.dumps(strengths or []),
                    json.dumps(weaknesses or []),
                    _now(),
                ),
            )
            return int(cursor.lastrowid)
    except Exception as exc:  # noqa: BLE001
        print(f"Save competitor error: {exc}")
        return None


def save_vendor(session_id: int, vendor: dict) -> Optional[int]:
    try:
        advantages = vendor.get("advantages", []) or []
        disadvantages = vendor.get("disadvantages", []) or []
        alternatives = vendor.get("alternatives_available")
        alternatives_bool = None if alternatives is None else bool(alternatives)

        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO vendors (
                    session_id,
                    vendor_name,
                    vendor_type,
                    importance,
                    advantages,
                    disadvantages,
                    alternatives_available,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    vendor.get("vendor_name"),
                    vendor.get("vendor_type"),
                    vendor.get("importance"),
                    json.dumps(advantages or []),
                    json.dumps(disadvantages or []),
                    alternatives_bool,
                    _now(),
                ),
            )
            return int(cursor.lastrowid)
    except Exception as exc:  # noqa: BLE001
        print(f"Save vendor error: {exc}")
        return None


def get_competitors(session_id: int) -> list[dict]:
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM competitors WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [
            {
                **dict(row),
                "strengths": json.loads(row["strengths"]) if row["strengths"] else [],
                "weaknesses": json.loads(row["weaknesses"]) if row["weaknesses"] else [],
            }
            for row in rows
        ]
    except Exception as exc:  # noqa: BLE001
        print(f"Get competitors error: {exc}")
        return []


def get_latest_business_analysis(session_id: int) -> Optional[dict]:
    try:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT * FROM business_analysis
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return dict(row) if row else None
    except Exception as exc:  # noqa: BLE001
        print(f"Get latest business analysis error: {exc}")
        return None


def get_latest_analysis(session_id: int) -> Optional[dict]:
    try:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT * FROM analysis_results
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return dict(row) if row else None
    except Exception as exc:  # noqa: BLE001
        print(f"Get latest analysis error: {exc}")
        return None


def save_critique(
    analysis_id: int,
    approved: bool,
    issues: list,
    adjustment: Optional[float],
) -> Optional[int]:
    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO critiques (analysis_id, approved, issues, confidence_adjustment, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (analysis_id, int(approved), json.dumps(issues or []), adjustment, _now()),
            )
            return int(cursor.lastrowid)
    except Exception as exc:  # noqa: BLE001
        print(f"Save critique error: {exc}")
        return None


def log_agent_activity(
    session_id: int,
    agent_name: str,
    message: str,
    status: str,
    metadata: Optional[dict] = None,
) -> None:
    try:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO agent_logs (session_id, agent_name, message, status, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, agent_name, message, status, json.dumps(metadata) if metadata else None, _now()),
            )
    except Exception as exc:  # noqa: BLE001
        print(f"Log agent activity error: {exc}")


def get_agent_logs(session_id: int, since_id: int = 0) -> list[dict]:
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM agent_logs
                WHERE session_id = ? AND id > ?
                ORDER BY id
                """,
                (session_id, since_id),
            ).fetchall()
        return [
            {
                **dict(row),
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
            }
            for row in rows
        ]
    except Exception as exc:  # noqa: BLE001
        print(f"Get agent logs error: {exc}")
        return []


def list_sessions() -> list[dict]:
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC",
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:  # noqa: BLE001
        print(f"List sessions error: {exc}")
        return []


def save_hallucination_warning(
    session_id: int,
    claim: str,
    issue: str,
    severity: str,
) -> Optional[int]:
    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO hallucination_warnings (session_id, claim, issue, severity, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, claim, issue, severity, _now()),
            )
            return int(cursor.lastrowid)
    except Exception as exc:  # noqa: BLE001
        print(f"Save hallucination warning error: {exc}")
        return None


def get_hallucination_warnings(session_id: int) -> list[dict]:
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM hallucination_warnings
                WHERE session_id = ?
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:  # noqa: BLE001
        print(f"Get hallucination warnings error: {exc}")
        return []


def save_decision_defense(
    session_id: int,
    recommendation: str,
    defenses: dict,
) -> Optional[int]:
    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO decision_defenses (
                    session_id,
                    recommendation,
                    why_not_stop,
                    why_not_investigate,
                    why_not_proceed,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    recommendation,
                    defenses.get("why_not_stop"),
                    defenses.get("why_not_investigate"),
                    defenses.get("why_not_proceed"),
                    _now(),
                ),
            )
            return int(cursor.lastrowid)
    except Exception as exc:  # noqa: BLE001
        print(f"Save decision defense error: {exc}")
        return None


def get_decision_defense(session_id: int) -> Optional[dict]:
    try:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT * FROM decision_defenses
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return dict(row) if row else None
    except Exception as exc:  # noqa: BLE001
        print(f"Get decision defense error: {exc}")
        return None


def save_business_metrics(session_id: int, strategy: dict) -> Optional[int]:
    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO business_metrics (
                    session_id,
                    breakeven_months_min,
                    breakeven_months_max,
                    breakeven_key_driver,
                    breakeven_assumptions,
                    primary_segment,
                    primary_segment_size,
                    secondary_segment,
                    poor_fit_segments,
                    segment_reasoning,
                    optimal_price_min,
                    optimal_price_max,
                    pricing_sensitivity,
                    price_points,
                    minimum_adoption_pct,
                    failure_threshold_pct,
                    adoption_kpi_description,
                    cost_per_unit,
                    revenue_per_unit,
                    gross_margin_pct,
                    unit_economics_health,
                    margin_buffer,
                    launch_approach,
                    launch_steps,
                    timeline_days,
                    early_failure_signals,
                    pivot_threshold_days,
                    comparable_businesses,
                    operational_complexity,
                    time_commitment,
                    automation_potential,
                    critical_skills,
                    pivot_suggestions,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    strategy["breakeven"]["months_min"],
                    strategy["breakeven"]["months_max"],
                    strategy["breakeven"]["key_driver"],
                    json.dumps(strategy["breakeven"]["assumptions"]),
                    strategy["customer_segments"]["primary"]["segment"],
                    strategy["customer_segments"]["primary"]["size"],
                    strategy["customer_segments"]["secondary"]["segment"],
                    json.dumps(strategy["customer_segments"]["poor_fit"]),
                    strategy["customer_segments"]["primary"]["reasoning"],
                    strategy["pricing"]["optimal_min"],
                    strategy["pricing"]["optimal_max"],
                    strategy["pricing"]["sensitivity"],
                    json.dumps(strategy["pricing"]["price_points"]),
                    strategy["adoption_threshold"]["minimum_adoption_pct"],
                    strategy["adoption_threshold"]["failure_threshold_pct"],
                    strategy["adoption_threshold"]["kpi"],
                    strategy["unit_economics"]["cost_per_unit"],
                    strategy["unit_economics"]["revenue_per_unit"],
                    strategy["unit_economics"]["gross_margin_pct"],
                    strategy["unit_economics"]["health"],
                    strategy["unit_economics"]["margin_buffer"],
                    strategy["launch_strategy"]["approach"],
                    json.dumps(strategy["launch_strategy"]["steps"]),
                    strategy["launch_strategy"]["total_timeline_days"],
                    json.dumps(strategy["failure_signals"]),
                    strategy.get("pivot_threshold_days", 14),
                    json.dumps(strategy["comparable_cases"]),
                    strategy["resource_requirements"]["operational_complexity"],
                    strategy["resource_requirements"]["time_commitment"],
                    strategy["resource_requirements"]["automation_potential"],
                    json.dumps(strategy["resource_requirements"]["critical_skills"]),
                    json.dumps(strategy.get("pivot_suggestions", [])),
                    _now(),
                ),
            )
            return int(cursor.lastrowid)
    except Exception as exc:  # noqa: BLE001
        print(f"Save business metrics error: {exc}")
        return None


def get_business_metrics(session_id: int) -> Optional[dict]:
    try:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT * FROM business_metrics
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        if not row:
            return None

        return _parse_metrics_json_fields(dict(row))
    except Exception as exc:  # noqa: BLE001
        print(f"Get business metrics error: {exc}")
        return None


def create_approval_gate(session_id: int, gate_type: str, description: str) -> Optional[int]:
    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO approval_gates (session_id, gate_type, description)
                VALUES (?, ?, ?)
                """,
                (session_id, gate_type, description),
            )
            return int(cursor.lastrowid)
    except Exception as exc:  # noqa: BLE001
        print(f"Create approval gate error: {exc}")
        return None


def get_pending_approvals(session_id: int) -> list[dict]:
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM approval_gates
                WHERE session_id = ? AND approved IS NULL
                ORDER BY created_at DESC
                """,
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:  # noqa: BLE001
        print(f"Get pending approvals error: {exc}")
        return []


def get_approval_gate(gate_id: int) -> Optional[dict]:
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM approval_gates WHERE id = ?",
                (gate_id,),
            ).fetchone()
        return dict(row) if row else None
    except Exception as exc:  # noqa: BLE001
        print(f"Get approval gate error: {exc}")
        return None


def respond_to_approval(gate_id: int, approved: bool, modifications: Optional[dict] = None) -> None:
    try:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE approval_gates
                SET approved = ?, user_modifications = ?, responded_at = ?
                WHERE id = ?
                """,
                (
                    int(bool(approved)),
                    json.dumps(modifications or {}),
                    _now(),
                    gate_id,
                ),
            )
    except Exception as exc:  # noqa: BLE001
        print(f"Respond to approval error: {exc}")


def save_uploaded_document(filename: str, file_type: str, content: str) -> Optional[int]:
    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO uploaded_documents (filename, file_type, content, uploaded_at)
                VALUES (?, ?, ?, ?)
                """,
                (filename, file_type, content, _now()),
            )
            return int(cursor.lastrowid)
    except Exception as exc:  # noqa: BLE001
        print(f"Save uploaded document error: {exc}")
        return None


def get_uploaded_document(doc_id: int) -> Optional[dict]:
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM uploaded_documents WHERE id = ?",
                (doc_id,),
            ).fetchone()
        return dict(row) if row else None
    except Exception as exc:  # noqa: BLE001
        print(f"Get uploaded document error: {exc}")
        return None


def get_uploaded_documents(doc_ids: list[int]) -> list[dict]:
    if not doc_ids:
        return []
    placeholders = ",".join(["?"] * len(doc_ids))
    try:
        with get_db() as conn:
            rows = conn.execute(
                f"SELECT * FROM uploaded_documents WHERE id IN ({placeholders})",
                doc_ids,
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:  # noqa: BLE001
        print(f"Get uploaded documents error: {exc}")
        return []


def create_shared_report(session_id: int, share_token: str) -> Optional[int]:
    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO shared_reports (session_id, share_token, created_at)
                VALUES (?, ?, ?)
                """,
                (session_id, share_token, _now()),
            )
            return int(cursor.lastrowid)
    except Exception as exc:  # noqa: BLE001
        print(f"Create shared report error: {exc}")
        return None


def get_shared_report_session(share_token: str) -> Optional[int]:
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT session_id FROM shared_reports WHERE share_token = ?",
                (share_token,),
            ).fetchone()
        return int(row["session_id"]) if row else None
    except Exception as exc:  # noqa: BLE001
        print(f"Get shared report error: {exc}")
        return None
