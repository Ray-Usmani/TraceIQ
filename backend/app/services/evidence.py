"""Evidence artifact models for SQL (and later Python) analysis results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class ColumnProfile(BaseModel):
    """Deterministic summary of one result column."""

    name: str
    dtype: Literal["numeric", "text", "timestamp", "other"] = "other"
    null_count: int = 0
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    top_values: list[dict[str, Any]] | None = None


class SqlArtifact(BaseModel):
    """Structured evidence produced by a SQL analysis step."""

    evidence_id: str
    step_id: str | None = None
    tool: str = "sql"
    question: str
    sql: str = ""
    reason: str = ""
    columns: list[str] = Field(default_factory=list)
    row_count: int = 0
    result_preview: list[dict[str, Any]] = Field(default_factory=list)
    column_profiles: list[ColumnProfile] = Field(default_factory=list)
    execution_ms: int = 0
    status: Literal["success", "error", "timeout"] = "success"
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
