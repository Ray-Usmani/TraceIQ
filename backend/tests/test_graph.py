"""Tests for Phase 3 graph sequencing and terminal states."""

from __future__ import annotations

from app.agent.graph import build_graph
from app.agent.nodes.router import finalize_node
from app.agent.runner import run_investigation
from app.agent.state import (
    IntakeResult,
    InvestigationPlan,
    InvestigationStep,
    StepOutcome,
)
from app.services.evidence import SqlArtifact
from app.services.run_registry import RunRegistry


def _intake_node(_state: object) -> dict[str, object]:
    return {
        "intake": IntakeResult(
            intent="diagnostic",
            relevant_tables=["orders"],
            relevant_metrics=["revenue"],
        ),
        "status": "running",
    }


def _context_node(_state: object) -> dict[str, object]:
    return {"schema_context": "orders schema", "metric_context": "revenue metric"}


def _planner_node(_state: object) -> dict[str, object]:
    return {
        "investigation_plan": InvestigationPlan(
            objective="Investigate revenue",
            steps=[
                InvestigationStep(id="step_1", question="First", purpose="Baseline"),
                InvestigationStep(id="step_2", question="Second", purpose="Segment"),
                InvestigationStep(id="step_3", question="Third", purpose="Validate"),
            ],
        ),
        "current_step_index": 0,
    }


def test_graph_runs_steps_in_order_and_continues_after_failure() -> None:
    calls: list[str] = []

    def sql_runner(question: str, **kwargs: object) -> SqlArtifact:
        calls.append(question)
        failed = question == "Second"
        return SqlArtifact(
            evidence_id=f"ev_{len(calls)}",
            step_id=str(kwargs["step_id"]),
            question=question,
            status="error" if failed else "success",
            error="query failed" if failed else None,
        )

    graph = build_graph(
        intake=_intake_node,
        context_loader=_context_node,
        planner=_planner_node,
        sql_runner=sql_runner,
    )
    result = graph.invoke(
        {
            "run_id": "run_1",
            "user_question": "Why?",
            "status": "running",
            "completed_steps": [],
            "evidence": [],
            "errors": [],
        }
    )

    assert calls == ["First", "Second", "Third"]
    assert result["status"] == "completed_with_errors"
    assert [artifact.step_id for artifact in result["evidence"]] == [
        "step_1",
        "step_2",
        "step_3",
    ]
    assert result["completed_steps"][1].status == "failed"


def test_graph_stops_after_material_ambiguity() -> None:
    def ambiguous(_state: object) -> dict[str, object]:
        return {
            "intake": IntakeResult(
                intent="comparative",
                ambiguities=["Comparison period is missing"],
            ),
            "status": "needs_clarification",
        }

    def should_not_run(_state: object) -> dict[str, object]:
        raise AssertionError("downstream node should not run")

    graph = build_graph(
        intake=ambiguous,
        context_loader=should_not_run,
        planner=should_not_run,
        sql_runner=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError()),
    )
    result = graph.invoke(
        {
            "run_id": "run_2",
            "user_question": "Compare revenue",
            "status": "running",
            "completed_steps": [],
            "evidence": [],
            "errors": [],
        }
    )

    assert result["status"] == "needs_clarification"


def test_background_runner_publishes_final_graph_snapshot() -> None:
    def sql_runner(question: str, **kwargs: object) -> SqlArtifact:
        return SqlArtifact(
            evidence_id=f"ev_{kwargs['step_id']}",
            step_id=str(kwargs["step_id"]),
            question=question,
        )

    graph = build_graph(
        intake=_intake_node,
        context_loader=_context_node,
        planner=_planner_node,
        sql_runner=sql_runner,
    )
    registry = RunRegistry()
    registry.create("run_3", "Why?")

    run_investigation("run_3", "Why?", registry=registry, graph=graph)
    snapshot = registry.get("run_3")

    assert snapshot.status == "completed"
    assert snapshot.current_step is None
    assert len(snapshot.completed_steps) == 3
    assert len(snapshot.evidence) == 3


def test_finalize_status_rules() -> None:
    success = StepOutcome(step_id="step_1", status="completed")
    failure = StepOutcome(step_id="step_2", status="failed")

    assert finalize_node({"completed_steps": [success]})["status"] == "completed"
    assert (
        finalize_node({"completed_steps": [success, failure]})["status"]
        == "completed_with_errors"
    )
    assert finalize_node({"completed_steps": [failure]})["status"] == "failed"
