"""Typed contracts shared by the Phase 3 investigation graph and API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, TypedDict

from pydantic import BaseModel, Field

from app.services.evidence import SqlArtifact

AnalysisIntent = Literal[
    "descriptive",
    "comparative",
    "diagnostic",
    "ranking",
    "trend",
    "funnel",
    "product_analysis",
    "marketing_analysis",
]
RunStatus = Literal[
    "queued",
    "running",
    "needs_clarification",
    "completed",
    "completed_with_errors",
    "failed",
]
StepStatus = Literal["running", "completed", "failed"]


class IntakeResult(BaseModel):
    """Structured understanding of the user's business question."""

    intent: AnalysisIntent
    primary_metric: str | None = None
    time_period: str | None = None
    comparison_period: str | None = None
    dimensions_to_consider: list[str] = Field(default_factory=list)
    relevant_tables: list[str] = Field(default_factory=list)
    relevant_metrics: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)


class PlannedStepDraft(BaseModel):
    """Planner output before the server assigns a stable step identifier."""

    question: str = Field(min_length=1)
    tool: Literal["sql"] = "sql"
    purpose: str = Field(min_length=1)


class PlannerOutput(BaseModel):
    """Validated LLM planner response."""

    objective: str = Field(min_length=1)
    steps: list[PlannedStepDraft] = Field(min_length=2, max_length=8)


class InvestigationStep(BaseModel):
    """One server-normalized investigation step."""

    id: str
    question: str
    tool: Literal["sql"] = "sql"
    purpose: str


class InvestigationPlan(BaseModel):
    """Fixed Phase 3 plan executed sequentially."""

    objective: str
    steps: list[InvestigationStep]


class StepOutcome(BaseModel):
    """Public execution outcome for a planned step."""

    step_id: str
    status: StepStatus
    evidence_id: str | None = None
    error: str | None = None


class AnalysisAccepted(BaseModel):
    """Response returned immediately after scheduling an investigation."""

    run_id: str
    status: Literal["queued"] = "queued"
    status_url: str


class AnalysisRunSnapshot(BaseModel):
    """Immutable public snapshot of an in-memory investigation run."""

    run_id: str
    question: str
    status: RunStatus
    intake: IntakeResult | None = None
    plan: InvestigationPlan | None = None
    current_step: InvestigationStep | None = None
    completed_steps: list[StepOutcome] = Field(default_factory=list)
    evidence: list[SqlArtifact] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AnalysisState(TypedDict, total=False):
    """Shared state for the sequential LangGraph investigation."""

    run_id: str
    user_question: str
    status: RunStatus
    intake: IntakeResult
    schema_context: str
    metric_context: str
    investigation_plan: InvestigationPlan
    current_step_index: int
    current_step: InvestigationStep | None
    completed_steps: list[StepOutcome]
    evidence: list[SqlArtifact]
    errors: list[str]
