"""Fixed SQL investigation planning node."""

from __future__ import annotations

from pathlib import Path

from app.agent.state import (
    AnalysisState,
    InvestigationPlan,
    InvestigationStep,
    PlannerOutput,
)
from app.config import get_settings
from app.llm.structured import call_structured

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "planner.md"


def planner_node(state: AnalysisState) -> dict[str, object]:
    """Create and normalize a bounded, SQL-only investigation plan."""
    settings = get_settings()
    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        max_steps=settings.analysis_max_steps,
        question=state["user_question"],
        intake=state["intake"].model_dump_json(indent=2),
        schema_context=state["schema_context"],
        metric_context=state["metric_context"],
    )
    output = call_structured(
        PlannerOutput,
        system_prompt=(
            "You design concise ecommerce investigations. Return valid JSON only. "
            "Plan SQL questions but never generate SQL."
        ),
        user_prompt=prompt,
        max_attempts=settings.structured_output_max_attempts,
    )
    if len(output.steps) > settings.analysis_max_steps:
        raise ValueError(
            f"Planner returned {len(output.steps)} steps; maximum is "
            f"{settings.analysis_max_steps}"
        )

    steps = [
        InvestigationStep(
            id=f"step_{index}",
            question=draft.question,
            tool=draft.tool,
            purpose=draft.purpose,
        )
        for index, draft in enumerate(output.steps, start=1)
    ]
    return {
        "investigation_plan": InvestigationPlan(
            objective=output.objective,
            steps=steps,
        ),
        "current_step_index": 0,
    }
