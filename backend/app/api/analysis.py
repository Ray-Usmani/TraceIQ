"""Asynchronous Phase 3 investigation creation and polling API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.agent.runner import run_investigation, run_registry
from app.agent.state import AnalysisAccepted, AnalysisRunSnapshot
from app.services.run_registry import RunCapacityError, RunNotFoundError

router = APIRouter(prefix="/api/v1", tags=["analysis"])


class AnalysisRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        """Reject whitespace-only questions and store a normalized value."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized


@router.post(
    "/analysis",
    response_model=AnalysisAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_analysis(
    req: AnalysisRequest,
    background_tasks: BackgroundTasks,
) -> AnalysisAccepted:
    """Queue an in-process investigation and return its polling location."""
    run_id = str(uuid.uuid4())
    try:
        run_registry.create(run_id, req.question)
    except RunCapacityError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc

    background_tasks.add_task(run_investigation, run_id, req.question)
    return AnalysisAccepted(
        run_id=run_id,
        status_url=f"/api/v1/analysis/{run_id}",
    )


@router.get("/analysis/{run_id}", response_model=AnalysisRunSnapshot)
def get_analysis(run_id: str) -> AnalysisRunSnapshot:
    """Return the latest immutable snapshot for a process-local run."""
    try:
        return run_registry.get(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run '{run_id}' was not found",
        ) from exc


@router.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: str) -> None:
    """Evidence persistence arrives in Phase 4."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            f"Evidence retrieval for '{evidence_id}' is not implemented yet. "
            "Phase 3 returns artifacts inline with the analysis run snapshot."
        ),
    )
