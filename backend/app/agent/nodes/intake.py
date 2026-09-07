"""Question-intake and semantic-context selection nodes."""

from __future__ import annotations

from pathlib import Path

from app.agent.state import AnalysisState, IntakeResult
from app.agent.tools.schema_tool import (
    available_metric_names,
    available_table_names,
    load_metrics_context,
    load_schema_context,
)
from app.config import get_settings
from app.llm.structured import call_structured

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "intake.md"


def intake_node(state: AnalysisState) -> dict[str, object]:
    """Classify a question and select valid semantic-layer names."""
    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        schema_context=load_schema_context(),
        metric_context=load_metrics_context(),
        question=state["user_question"],
    )
    intake = call_structured(
        IntakeResult,
        system_prompt=(
            "You classify ecommerce analytics questions. Return valid JSON only "
            "and never invent tables or metrics."
        ),
        user_prompt=prompt,
        max_attempts=get_settings().structured_output_max_attempts,
    )

    table_names = available_table_names()
    metric_names = available_metric_names()
    invalid_tables = sorted(set(intake.relevant_tables) - set(table_names))
    invalid_metrics = sorted(set(intake.relevant_metrics) - set(metric_names))
    if invalid_tables or invalid_metrics:
        parts: list[str] = []
        if invalid_tables:
            parts.append(f"unknown tables: {', '.join(invalid_tables)}")
        if invalid_metrics:
            parts.append(f"unknown metrics: {', '.join(invalid_metrics)}")
        raise ValueError("Intake selected " + "; ".join(parts))

    if not intake.relevant_tables:
        intake.relevant_tables = table_names
    if not intake.relevant_metrics:
        intake.relevant_metrics = metric_names

    status = "needs_clarification" if intake.ambiguities else "running"
    return {"intake": intake, "status": status}


def route_after_intake(state: AnalysisState) -> str:
    """Stop material ambiguity before any plan or query is produced."""
    return "clarify" if state["status"] == "needs_clarification" else "continue"


def load_context_node(state: AnalysisState) -> dict[str, str]:
    """Render only the schema and metric context selected during intake."""
    intake = state["intake"]
    return {
        "schema_context": load_schema_context(intake.relevant_tables),
        "metric_context": load_metrics_context(intake.relevant_metrics),
    }
