"""Unit tests for intake, semantic filtering, and plan normalization."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.nodes import intake as intake_module
from app.agent.nodes import planner as planner_module
from app.agent.state import IntakeResult, PlannedStepDraft, PlannerOutput


def _intake(**overrides: object) -> IntakeResult:
    values: dict[str, object] = {
        "intent": "diagnostic",
        "primary_metric": "conversion_rate",
        "relevant_tables": ["website_sessions", "orders"],
        "relevant_metrics": ["sessions", "orders", "conversion_rate"],
    }
    values.update(overrides)
    return IntakeResult.model_validate(values)


def test_intake_rejects_invented_semantic_names(monkeypatch: object) -> None:
    result = _intake(relevant_tables=["invented_table"])
    monkeypatch.setattr(intake_module, "call_structured", lambda *a, **k: result)

    with pytest.raises(ValueError, match="unknown tables: invented_table"):
        intake_module.intake_node({"user_question": "Why?"})


def test_intake_empty_selection_falls_back_to_all_context(
    monkeypatch: object,
) -> None:
    result = _intake(relevant_tables=[], relevant_metrics=[])
    monkeypatch.setattr(intake_module, "call_structured", lambda *a, **k: result)

    update = intake_module.intake_node({"user_question": "Show performance"})
    intake = update["intake"]

    assert isinstance(intake, IntakeResult)
    assert "website_sessions" in intake.relevant_tables
    assert "conversion_rate" in intake.relevant_metrics


def test_context_loader_includes_only_selected_tables_and_metrics() -> None:
    update = intake_module.load_context_node(
        {
            "intake": _intake(
                relevant_tables=["website_sessions", "orders"],
                relevant_metrics=["conversion_rate"],
            )
        }
    )

    assert "analytics.website_sessions" in update["schema_context"]
    assert "analytics.orders" in update["schema_context"]
    assert "analytics.products" not in update["schema_context"]
    assert "conversion_rate" in update["metric_context"]
    assert "refund_rate" not in update["metric_context"]


def test_material_ambiguity_routes_to_clarification(monkeypatch: object) -> None:
    result = _intake(ambiguities=["Which year does Q3 refer to?"])
    monkeypatch.setattr(intake_module, "call_structured", lambda *a, **k: result)
    update = intake_module.intake_node({"user_question": "What happened in Q3?"})

    assert update["status"] == "needs_clarification"
    assert intake_module.route_after_intake(update) == "clarify"


def test_planner_assigns_stable_server_step_ids(monkeypatch: object) -> None:
    output = PlannerOutput(
        objective="Explain conversion",
        steps=[
            PlannedStepDraft(question="Baseline conversion", purpose="Verify change"),
            PlannedStepDraft(question="Conversion by source", purpose="Segment change"),
        ],
    )
    monkeypatch.setattr(planner_module, "call_structured", lambda *a, **k: output)
    state = {
        "user_question": "Why did conversion decline?",
        "intake": _intake(),
        "schema_context": "schema",
        "metric_context": "metrics",
    }

    update = planner_module.planner_node(state)
    plan = update["investigation_plan"]

    assert [step.id for step in plan.steps] == ["step_1", "step_2"]
    assert all(step.tool == "sql" for step in plan.steps)


def test_planner_contract_rejects_non_sql_tool() -> None:
    with pytest.raises(ValidationError):
        PlannerOutput.model_validate(
            {
                "objective": "Bad plan",
                "steps": [
                    {"question": "One", "purpose": "One", "tool": "python"},
                    {"question": "Two", "purpose": "Two", "tool": "sql"},
                ],
            }
        )


def test_planner_contract_enforces_hard_step_limit() -> None:
    with pytest.raises(ValidationError):
        PlannerOutput(
            objective="Too large",
            steps=[
                PlannedStepDraft(question=f"Question {index}", purpose="Test")
                for index in range(9)
            ],
        )
