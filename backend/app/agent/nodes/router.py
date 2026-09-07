"""Sequential Phase 3 step selection, execution, and finalization."""

from __future__ import annotations

from collections.abc import Callable

from app.agent.state import AnalysisState, StepOutcome, StepStatus
from app.services.evidence import SqlArtifact

SqlRunner = Callable[..., SqlArtifact]


def select_step_node(state: AnalysisState) -> dict[str, object]:
    """Select the next step in order, or clear it when the plan is exhausted."""
    index = state.get("current_step_index", 0)
    steps = state["investigation_plan"].steps
    if index >= len(steps):
        return {"current_step": None}
    return {"current_step": steps[index]}


def route_current_step(state: AnalysisState) -> str:
    """Route the selected tool; Python is intentionally unavailable in Phase 3."""
    step = state.get("current_step")
    if step is None:
        return "finalize"
    return step.tool


def execute_sql_node(
    state: AnalysisState,
    *,
    sql_runner: SqlRunner,
) -> dict[str, object]:
    """Execute one SQL step and record its artifact without aborting later steps."""
    step = state["current_step"]
    if step is None:
        raise ValueError("SQL execution requested without a current step")

    artifact = sql_runner(
        step.question,
        step_id=step.id,
        schema_context=state["schema_context"],
        metric_context=state["metric_context"],
    )
    outcome_status: StepStatus = (
        "completed" if artifact.status == "success" else "failed"
    )
    outcome = StepOutcome(
        step_id=step.id,
        status=outcome_status,
        evidence_id=artifact.evidence_id,
        error=artifact.error,
    )
    errors = list(state.get("errors", []))
    if artifact.status != "success":
        errors.append(f"{step.id}: {artifact.error or artifact.status}")

    return {
        "evidence": [*state.get("evidence", []), artifact],
        "completed_steps": [*state.get("completed_steps", []), outcome],
        "errors": errors,
        "current_step_index": state.get("current_step_index", 0) + 1,
    }


def finalize_node(state: AnalysisState) -> dict[str, object]:
    """Derive the terminal run status from all SQL step outcomes."""
    outcomes = state.get("completed_steps", [])
    succeeded = sum(outcome.status == "completed" for outcome in outcomes)
    failed = sum(outcome.status == "failed" for outcome in outcomes)
    if succeeded and failed:
        status = "completed_with_errors"
    elif succeeded:
        status = "completed"
    else:
        status = "failed"
    return {"status": status, "current_step": None}
