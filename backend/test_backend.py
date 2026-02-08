from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx


DEFAULT_BASE_URL = os.getenv("MANAGERGPT_BASE_URL", "http://localhost:8000").rstrip("/")


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def _fail(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(1)


def _request_json(client: httpx.Client, method: str, url: str, **kwargs: Any) -> Tuple[int, Any]:
    resp = client.request(method, url, **kwargs)
    try:
        payload = resp.json()
    except Exception:
        payload = resp.text
    return resp.status_code, payload


def _parse_sse_event_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line:
        return None
    if line.startswith(":"):
        return None
    if not line.startswith("data:"):
        return None

    raw = line[len("data:") :].strip()
    if not raw:
        return None

    try:
        return json.loads(raw)
    except Exception:
        return {"_raw": raw}


def _wait_for_completion_via_sse(
    client: httpx.Client,
    session_id: int,
    max_seconds: float = 120.0,
) -> List[Dict[str, Any]]:
    url = f"{DEFAULT_BASE_URL}/api/stream/{session_id}"
    events: List[Dict[str, Any]] = []
    started = time.time()

    with client.stream("GET", url) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if time.time() - started > max_seconds:
                break
            if not line:
                continue
            event = _parse_sse_event_line(line)
            if not event:
                continue
            events.append(event)

            agent = str(event.get("agent", ""))
            status = str(event.get("status", ""))
            message = str(event.get("message", ""))

            # The orchestrator always logs a final System decision like:
            # "Decision: PROCEED (55% confidence)"
            if agent == "System" and status in {"complete", "completed"} and message.startswith("Decision:"):
                break

    return events


def main() -> None:
    print(f"Base URL: {DEFAULT_BASE_URL}")

    checks: List[CheckResult] = []

    timeout = httpx.Timeout(connect=5.0, read=60.0, write=20.0, pool=5.0)
    with httpx.Client(timeout=timeout) as client:
        # 1) POST /api/execute
        goal = os.getenv(
            "MANAGERGPT_TEST_GOAL",
            "Should I launch an AI tutoring app for high schoolers?",
        )
        status, payload = _request_json(
            client,
            "POST",
            f"{DEFAULT_BASE_URL}/api/execute",
            headers={"Content-Type": "application/json"},
            json={"goal": goal},
        )

        if status != 200 or not isinstance(payload, dict) or "session_id" not in payload:
            checks.append(CheckResult("POST /api/execute", False, f"HTTP {status}: {payload}"))
            for c in checks:
                print(f"[{ 'OK' if c.ok else 'FAIL' }] {c.name} {c.detail}")
            _fail("Execute endpoint failed; is the backend running on port 8000?")

        session_id = int(payload["session_id"])
        checks.append(CheckResult("POST /api/execute", True, f"session_id={session_id}"))

        # 2) GET /api/stream/{id} (SSE)
        try:
            events = _wait_for_completion_via_sse(client, session_id)
            if not events:
                checks.append(CheckResult("GET /api/stream/{id}", False, "No SSE events received"))
            else:
                last = events[-1]
                checks.append(
                    CheckResult(
                        "GET /api/stream/{id}",
                        True,
                        f"events={len(events)} last_agent={last.get('agent')} last_status={last.get('status')}",
                    )
                )
        except Exception as exc:
            checks.append(CheckResult("GET /api/stream/{id}", False, f"{type(exc).__name__}: {exc}"))

        # 3) GET /api/session/{id}
        status, session_payload = _request_json(
            client,
            "GET",
            f"{DEFAULT_BASE_URL}/api/session/{session_id}",
        )
        if status != 200 or not isinstance(session_payload, dict):
            checks.append(CheckResult("GET /api/session/{id}", False, f"HTTP {status}: {session_payload}"))
        else:
            status_value = session_payload.get("status")
            final_decision = session_payload.get("final_decision")
            confidence = session_payload.get("confidence_score")
            checks.append(
                CheckResult(
                    "GET /api/session/{id}",
                    True,
                    f"status={status_value} decision={final_decision} confidence={confidence}",
                )
            )

        # 4) GET /api/sessions
        status, sessions_payload = _request_json(client, "GET", f"{DEFAULT_BASE_URL}/api/sessions")
        if status != 200 or not isinstance(sessions_payload, list):
            checks.append(CheckResult("GET /api/sessions", False, f"HTTP {status}: {sessions_payload}"))
        else:
            found = any(isinstance(item, dict) and int(item.get("session_id", -1)) == session_id for item in sessions_payload)
            checks.append(CheckResult("GET /api/sessions", found, f"found_session={found} total={len(sessions_payload)}"))

    # Print results
    failed = [c for c in checks if not c.ok]
    for c in checks:
        print(f"[{ 'OK' if c.ok else 'FAIL' }] {c.name} {c.detail}")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
