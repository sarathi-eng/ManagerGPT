from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import database
from backend import main as app_main


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "managergpt-test.db"))
    monkeypatch.setattr(
        database,
        "SCHEMA_PATH",
        str(Path(__file__).resolve().parents[2] / "schema.sql"),
    )
    monkeypatch.setattr(app_main, "_run_orchestrator", lambda *args, **kwargs: None)

    database.init_db()
    with TestClient(app_main.app) as test_client:
        yield test_client


def _create_session(goal: str = "Test business idea") -> int:
    session_id = database.create_session(goal)
    assert session_id is not None
    return session_id


def test_execute_goal_returns_session_id(client: TestClient) -> None:
    response = client.post("/api/execute", json={"goal": "Validate market demand"})

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["session_id"], int)


def test_get_session_returns_404_for_unknown_session(client: TestClient) -> None:
    response = client.get("/api/session/99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"


def test_list_sessions_includes_created_session(client: TestClient) -> None:
    session_id = _create_session()

    response = client.get("/api/sessions")

    assert response.status_code == 200
    sessions = response.json()
    assert any(item["session_id"] == session_id for item in sessions)


def test_share_link_and_report_endpoint(client: TestClient) -> None:
    session_id = _create_session("Should we launch in a new city?")

    share_response = client.post(f"/api/session/{session_id}/share")
    assert share_response.status_code == 200

    share_url = share_response.json()["share_url"]
    token = share_url.rsplit("/", 1)[-1]

    report_response = client.get(f"/report/{token}")
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["session_id"] == session_id


def test_upload_text_document(client: TestClient) -> None:
    files = {"file": ("notes.txt", b"sample manager notes", "text/plain")}

    response = client.post("/api/upload", files=files)

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "notes.txt"
    assert payload["file_type"] == "txt"
    assert isinstance(payload["document_id"], int)


def test_pending_approvals_and_respond(client: TestClient) -> None:
    session_id = _create_session("Need approval flow")
    gate_id = database.create_approval_gate(
        session_id=session_id,
        gate_type="research_plan",
        description="Approve research scope",
    )
    assert gate_id is not None

    pending_response = client.get(f"/api/approvals/{session_id}/pending")
    assert pending_response.status_code == 200
    pending = pending_response.json()
    assert len(pending) == 1
    assert pending[0]["id"] == gate_id

    respond_response = client.post(
        f"/api/approvals/{gate_id}/respond",
        json={"approved": True, "modifications": {"notes": "Looks good"}},
    )
    assert respond_response.status_code == 200
    assert respond_response.json()["status"] == "success"

    pending_after_response = client.get(f"/api/approvals/{session_id}/pending")
    assert pending_after_response.status_code == 200
    assert pending_after_response.json() == []
