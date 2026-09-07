"""SQL analysis tool: generate, validate, execute, profile, and package results."""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.agent.tools.schema_tool import load_metrics_context, load_schema_context
from app.agent.tools.sql_validator import validate
from app.config import get_settings
from app.db.reader import QueryResult, execute_readonly_query
from app.llm.client import get_llm_client
from app.services.evidence import ColumnProfile, SqlArtifact

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "sql_generator.md"
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_PREVIEW_ROWS = 50


def _load_prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _format_prompt(
    question: str,
    repair_context: str | None = None,
    *,
    schema_context: str | None = None,
    metric_context: str | None = None,
) -> str:
    template = _load_prompt_template()
    prompt = template.format(
        schema_context=schema_context or load_schema_context(),
        metrics_context=metric_context or load_metrics_context(),
        question=question,
    )
    if repair_context:
        prompt += (
            "\n\n## Previous Attempt Failed\n\n"
            f"{repair_context}\n\n"
            "Generate a corrected SQL query that fixes the error.\n"
        )
    return prompt


def _parse_llm_json(content: str) -> dict[str, Any]:
    text = content.strip()
    match = _JSON_BLOCK_RE.search(text)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


def _call_llm(prompt: str) -> dict[str, Any]:
    settings = get_settings()
    client = get_llm_client()

    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You generate safe, read-only PostgreSQL analytics SQL. "
                    "Respond with JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    if settings.llm_json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or "{}"
    return _parse_llm_json(content)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _is_timestamp(value: Any) -> bool:
    return isinstance(value, (datetime, date)) or (
        isinstance(value, str)
        and len(value) >= 10
        and value[4:5] == "-"
        and value[7:8] == "-"
    )


def profile_result(columns: list[str], rows: list[dict[str, Any]]) -> list[ColumnProfile]:
    """Deterministic column profiling (no LLM)."""
    profiles: list[ColumnProfile] = []
    for col in columns:
        values = [row.get(col) for row in rows]
        null_count = sum(1 for v in values if v is None)
        non_null = [v for v in values if v is not None]

        if not non_null:
            profiles.append(
                ColumnProfile(name=col, dtype="other", null_count=null_count)
            )
            continue

        if all(_is_number(v) for v in non_null):
            nums = [float(v) for v in non_null]
            profiles.append(
                ColumnProfile(
                    name=col,
                    dtype="numeric",
                    null_count=null_count,
                    min=min(nums),
                    max=max(nums),
                    mean=sum(nums) / len(nums),
                )
            )
        elif all(_is_timestamp(v) for v in non_null):
            profiles.append(
                ColumnProfile(name=col, dtype="timestamp", null_count=null_count)
            )
        else:
            counter = Counter(str(v) for v in non_null)
            top = [
                {"value": value, "count": count}
                for value, count in counter.most_common(5)
            ]
            profiles.append(
                ColumnProfile(
                    name=col,
                    dtype="text",
                    null_count=null_count,
                    top_values=top,
                )
            )
    return profiles


def _new_evidence_id() -> str:
    return f"ev_{uuid.uuid4().hex[:8]}"


def _error_artifact(
    question: str,
    *,
    step_id: str | None = None,
    sql: str = "",
    reason: str = "",
    error: str,
    status: str = "error",
    execution_ms: int = 0,
) -> SqlArtifact:
    return SqlArtifact(
        evidence_id=_new_evidence_id(),
        step_id=step_id,
        question=question,
        sql=sql,
        reason=reason,
        status=status,  # type: ignore[arg-type]
        error=error,
        execution_ms=execution_ms,
    )


def _success_artifact(
    question: str,
    sql: str,
    reason: str,
    query_result: QueryResult,
    *,
    step_id: str | None = None,
) -> SqlArtifact:
    profiles = profile_result(query_result.columns, query_result.rows)
    return SqlArtifact(
        evidence_id=_new_evidence_id(),
        step_id=step_id,
        question=question,
        sql=sql,
        reason=reason,
        columns=query_result.columns,
        row_count=query_result.row_count,
        result_preview=query_result.rows[:_PREVIEW_ROWS],
        column_profiles=profiles,
        execution_ms=query_result.execution_ms,
        status="success",
    )


def _generate_and_validate(
    question: str,
    repair_context: str | None = None,
    *,
    step_id: str | None = None,
    schema_context: str | None = None,
    metric_context: str | None = None,
) -> tuple[str, str, list[str]] | SqlArtifact:
    """Return (sql, reason, expected_columns) or an error artifact."""
    prompt = _format_prompt(
        question,
        repair_context=repair_context,
        schema_context=schema_context,
        metric_context=metric_context,
    )
    try:
        payload = _call_llm(prompt)
    except Exception as exc:
        logger.exception("LLM SQL generation failed")
        return _error_artifact(
            question,
            step_id=step_id,
            error=f"LLM generation failed: {exc}",
        )

    sql = (payload.get("sql") or "").strip()
    reason = (payload.get("reason") or "").strip()
    expected_columns = payload.get("expected_columns") or []
    if not isinstance(expected_columns, list):
        expected_columns = []

    if not sql:
        return _error_artifact(
            question,
            step_id=step_id,
            reason=reason,
            error="LLM returned empty SQL",
        )

    validation = validate(sql)
    if not validation.valid:
        return _error_artifact(
            question,
            step_id=step_id,
            sql=sql,
            reason=reason,
            error=f"SQL validation failed: {validation.error}",
        )

    return validation.sql, reason, [str(c) for c in expected_columns]


def run_sql_analysis(
    question: str,
    *,
    step_id: str | None = None,
    schema_context: str | None = None,
    metric_context: str | None = None,
) -> SqlArtifact:
    """
    End-to-end Phase 2 pipeline:

    context -> LLM SQL -> validate -> execute (as analytics_reader) -> profile -> artifact

    Retries with repair prompts on execution failure (max sql_max_repair_attempts).
    """
    settings = get_settings()
    question = question.strip()
    if not question:
        return _error_artifact(
            question,
            step_id=step_id,
            error="Question must not be empty",
        )

    generated = _generate_and_validate(
        question,
        step_id=step_id,
        schema_context=schema_context,
        metric_context=metric_context,
    )
    if isinstance(generated, SqlArtifact):
        return generated

    sql, reason, _expected = generated
    attempts = 0
    last_result: QueryResult | None = None

    while True:
        result = execute_readonly_query(sql)
        last_result = result
        if result.status == "success":
            artifact = _success_artifact(
                question,
                sql,
                reason,
                result,
                step_id=step_id,
            )
            logger.info(
                {
                    "node": "sql_tool",
                    "evidence_id": artifact.evidence_id,
                    "rows": artifact.row_count,
                    "execution_ms": artifact.execution_ms,
                    "success": True,
                }
            )
            return artifact

        attempts += 1
        if attempts > settings.sql_max_repair_attempts:
            break

        repair_context = (
            f"Failed SQL:\n{sql}\n\n"
            f"Database error ({result.status}): {result.error}"
        )
        logger.info(
            {
                "node": "sql_repair",
                "attempt": attempts,
                "error": result.error,
            }
        )
        repaired = _generate_and_validate(
            question,
            repair_context=repair_context,
            step_id=step_id,
            schema_context=schema_context,
            metric_context=metric_context,
        )
        if isinstance(repaired, SqlArtifact):
            # Validation/LLM failed during repair — keep trying only if attempts remain.
            if attempts >= settings.sql_max_repair_attempts:
                return repaired
            continue
        sql, reason, _expected = repaired

    assert last_result is not None
    return _error_artifact(
        question,
        step_id=step_id,
        sql=sql,
        reason=reason,
        error=last_result.error or "SQL execution failed",
        status=(
            last_result.status
            if last_result.status in {"error", "timeout"}
            else "error"
        ),
        execution_ms=last_result.execution_ms,
    )
