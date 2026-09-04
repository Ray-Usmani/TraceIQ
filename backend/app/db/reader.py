"""Read-only database access for LLM-generated analytics SQL."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings

logger = logging.getLogger(__name__)

_LIMIT_RE = re.compile(r"\blimit\b", re.IGNORECASE)


@dataclass
class QueryResult:
    """Outcome of a read-only SQL execution."""

    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    execution_ms: int = 0
    status: str = "success"  # success | error | timeout
    error: str | None = None
    sql_executed: str = ""


def _build_reader_engine() -> Engine:
    settings = get_settings()
    timeout_ms = settings.sql_statement_timeout_ms
    return create_engine(
        settings.reader_database_url,
        pool_pre_ping=True,
        connect_args={"options": f"-c statement_timeout={timeout_ms}"},
    )


reader_engine: Engine = _build_reader_engine()


def _ensure_row_limit(sql: str, max_rows: int) -> str:
    """Wrap SQL in an outer SELECT ... LIMIT if no LIMIT is present."""
    stripped = sql.strip().rstrip(";")
    if _LIMIT_RE.search(stripped):
        return stripped
    return f"SELECT * FROM ({stripped}) AS _traceiq_limited LIMIT {max_rows}"


def execute_readonly_query(
    sql: str,
    max_rows: int | None = None,
) -> QueryResult:
    """
    Execute a single SQL statement as analytics_reader.

    Applies statement_timeout via connection options and caps returned rows.
    Never uses the admin engine.
    """
    settings = get_settings()
    if max_rows is None:
        max_rows = settings.sql_max_rows

    limited_sql = _ensure_row_limit(sql, max_rows)
    started = time.perf_counter()

    try:
        with reader_engine.connect() as conn:
            result = conn.execute(text(limited_sql))
            columns = list(result.keys())
            raw_rows = result.fetchmany(max_rows)
            rows: list[dict[str, Any]] = []
            for row in raw_rows:
                mapping = dict(row._mapping)
                # Make values JSON-serializable
                cleaned: dict[str, Any] = {}
                for key, value in mapping.items():
                    if hasattr(value, "isoformat"):
                        cleaned[key] = value.isoformat()
                    elif isinstance(value, (bytes, memoryview)):
                        cleaned[key] = str(value)
                    else:
                        cleaned[key] = value
                rows.append(cleaned)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            {
                "node": "sql_executor",
                "duration_ms": elapsed_ms,
                "rows": len(rows),
                "success": True,
            }
        )
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_ms=elapsed_ms,
            status="success",
            sql_executed=limited_sql,
        )
    except SQLAlchemyError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = str(exc.__cause__ or exc)
        is_timeout = "timeout" in message.lower() or "canceling statement" in message.lower()
        status = "timeout" if is_timeout else "error"
        logger.warning(
            {
                "node": "sql_executor",
                "duration_ms": elapsed_ms,
                "success": False,
                "error": message,
                "status": status,
            }
        )
        return QueryResult(
            execution_ms=elapsed_ms,
            status=status,
            error=message,
            sql_executed=limited_sql,
        )
