"""SQL safety validation using SQLGlot AST analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

# Statement / expression types that must never be executed.
_FORBIDDEN_ROOT_OR_NODE: list[type] = [
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Grant,
    exp.Revoke,
    exp.Command,  # CALL, VACUUM, etc.
    exp.Set,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
]

for _name in ("TruncateTable", "Truncate", "Copy", "Kill", "Refresh"):
    _cls = getattr(exp, _name, None)
    if _cls is not None:
        _FORBIDDEN_ROOT_OR_NODE.append(_cls)

_FORBIDDEN_TYPES = tuple(_FORBIDDEN_ROOT_OR_NODE)


@dataclass
class ValidationResult:
    """Outcome of SQL safety validation."""

    valid: bool
    sql: str
    error: str | None = None
    statement_type: str | None = None
    tables_referenced: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _split_statements(sql: str) -> list[str]:
    """Split on semicolons into non-empty statements (naive but sufficient pre-check)."""
    parts = [p.strip() for p in sql.split(";")]
    return [p for p in parts if p]


def _collect_tables(expression: exp.Expression) -> list[str]:
    tables: list[str] = []
    for table in expression.find_all(exp.Table):
        name = table.sql(dialect="postgres")
        tables.append(name)
    return tables


def _has_forbidden_nodes(expression: exp.Expression) -> str | None:
    for node in expression.walk():
        if isinstance(node, _FORBIDDEN_TYPES):
            return f"Forbidden statement type: {type(node).__name__}"
        # SELECT INTO creates a new table — treat as write.
        if isinstance(node, exp.Select) and node.args.get("into") is not None:
            return "SELECT INTO is not allowed (creates a table)"
    return None


def validate(sql: str) -> ValidationResult:
    """
    Validate that SQL is a single read-only SELECT / WITH ... SELECT.

    Uses SQLGlot AST checks — not regex — for safety decisions.
    """
    cleaned = sql.strip()
    if not cleaned:
        return ValidationResult(valid=False, sql=cleaned, error="Empty SQL")

    statements = _split_statements(cleaned)
    if len(statements) > 1:
        return ValidationResult(
            valid=False,
            sql=cleaned,
            error="Multiple SQL statements are not allowed",
        )

    single = statements[0]

    try:
        parsed = sqlglot.parse(single, dialect="postgres")
    except ParseError as exc:
        return ValidationResult(
            valid=False,
            sql=single,
            error=f"SQL parse error: {exc}",
        )

    if not parsed or parsed[0] is None:
        return ValidationResult(
            valid=False,
            sql=single,
            error="SQL parse produced no expression",
        )

    if len(parsed) > 1:
        return ValidationResult(
            valid=False,
            sql=single,
            error="Multiple SQL statements are not allowed",
        )

    expression = cast(exp.Expression, parsed[0])

    forbidden = _has_forbidden_nodes(expression)
    if forbidden:
        return ValidationResult(
            valid=False,
            sql=single,
            error=forbidden,
            statement_type=type(expression).__name__,
        )

    if not isinstance(expression, exp.Select):
        # WITH ... SELECT is still a Select at the root in sqlglot.
        return ValidationResult(
            valid=False,
            sql=single,
            error=f"Only SELECT (including WITH ... SELECT) is allowed; got {type(expression).__name__}",
            statement_type=type(expression).__name__,
        )

    tables = _collect_tables(expression)
    warnings: list[str] = []
    for table_sql in tables:
        # table_sql may be "analytics.website_sessions" or just "website_sessions"
        if "." not in table_sql and not table_sql.startswith('"'):
            warnings.append(
                f"Table '{table_sql}' is missing the analytics. schema prefix"
            )

    try:
        normalized = expression.sql(dialect="postgres")
    except Exception:  # noqa: BLE001 -- preserve executable SQL if normalization fails
        normalized = single

    return ValidationResult(
        valid=True,
        sql=normalized,
        statement_type="Select",
        tables_referenced=tables,
        warnings=warnings,
    )
