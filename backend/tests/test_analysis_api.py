"""API tests for asynchronous investigation creation and polling."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.agent.state import IntakeResult
from app.api import analysis as analysis_api
from app.main import app
from app.services.run_registry import RunRegistry

client = TestClient(app)


def test_create_and_poll_completed_analysis(monkeypatch: object) -> None:
    registry = RunRegistry()

    def complete(run_id: str, question: str) -> None:
        registry.update_from_state(
            run_id,
            {
                "user_question": question,
                "status": "completed",
                "completed_steps": [],
                "evidence": [],
                "errors": [],
            },
        )

    monkeypatch.setattr(analysis_api, "run_registry", registry)
    monkeypatch.setattr(analysis_api, "run_investigation", complete)

    response = client.post("/api/v1/analysis", json={"question": "  Revenue trend  "})

    assert response.status_code == 202
    accepted = response.json()
    assert accepted["status"] == "queued"
    assert accepted["status_url"].endswith(accepted["run_id"])

    polled = client.get(accepted["status_url"])
    assert polled.status_code == 200
    assert polled.json()["status"] == "completed"
    assert polled.json()["question"] == "Revenue trend"


def test_poll_returns_clarification_details(monkeypatch: object) -> None:
    registry = RunRegistry()

    def clarify(run_id: str, question: str) -> None:
        registry.update_from_state(
            run_id,
            {
                "user_question": question,
                "status": "needs_clarification",
                "intake": IntakeResult(
                    intent="comparative",
                    ambiguities=["Which comparison period should be used?"],
                ),
            },
        )

    monkeypatch.setattr(analysis_api, "run_registry", registry)
    monkeypatch.setattr(analysis_api, "run_investigation", clarify)

    response = client.post("/api/v1/analysis", json={"question": "Compare revenue"})
    polled = client.get(response.json()["status_url"])

    assert polled.json()["status"] == "needs_clarification"
    assert polled.json()["intake"]["ambiguities"]


def test_create_returns_429_at_active_capacity(monkeypatch: object) -> None:
    registry = RunRegistry(max_active_runs=1)
    monkeypatch.setattr(analysis_api, "run_registry", registry)
    monkeypatch.setattr(analysis_api, "run_investigation", lambda *_args: None)

    first = client.post("/api/v1/analysis", json={"question": "First"})
    second = client.post("/api/v1/analysis", json={"question": "Second"})

    assert first.status_code == 202
    assert second.status_code == 429


def test_poll_unknown_run_returns_404(monkeypatch: object) -> None:
    monkeypatch.setattr(analysis_api, "run_registry", RunRegistry())

    response = client.get("/api/v1/analysis/missing")

    assert response.status_code == 404


def test_rejects_blank_question() -> None:
    response = client.post("/api/v1/analysis", json={"question": "   "})
    assert response.status_code == 422
