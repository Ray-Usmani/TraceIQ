"""Analysis API — Phase 2 safe SQL analyst endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agent.tools.sql_tool import run_sql_analysis
from app.services.evidence import SqlArtifact

router = APIRouter(prefix="/api/v1", tags=["analysis"])


class AnalysisRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)


class AnalysisResponse(BaseModel):
    evidence: SqlArtifact


@router.post("/analysis", response_model=AnalysisResponse)
async def run_analysis(req: AnalysisRequest) -> AnalysisResponse:
    """Run a single-question SQL analysis (generate -> validate -> execute)."""
    artifact = run_sql_analysis(req.question)
    return AnalysisResponse(evidence=artifact)


@router.get("/evidence/{evidence_id}")
async def get_evidence(evidence_id: str) -> None:
    """Evidence persistence arrives in Phase 4."""
    raise HTTPException(
        status_code=501,
        detail=(
            f"Evidence retrieval for '{evidence_id}' is not implemented yet. "
            "Artifacts are returned inline from POST /api/v1/analysis in Phase 2."
        ),
    )
