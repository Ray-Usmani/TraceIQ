"""Integration tests for schema context and read-only SQL execution."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.agent.tools.schema_tool import load_metrics_context, load_schema_context
from app.db.reader import execute_readonly_query, reader_engine


@pytest.mark.integration
def test_schema_context_contains_tables() -> None:
    text_ctx = load_schema_context()
    assert "analytics.website_sessions" in text_ctx
    assert "analytics.orders" in text_ctx
    assert "Grain:" in text_ctx
    assert "Joins" in text_ctx


@pytest.mark.integration
def test_metrics_context_contains_conversion_rate() -> None:
    text_ctx = load_metrics_context()
    assert "conversion_rate" in text_ctx
    assert "sessions" in text_ctx


@pytest.mark.integration
def test_readonly_query_counts_products() -> None:
    result = execute_readonly_query(
        "SELECT COUNT(*) AS product_count FROM analytics.products"
    )
    assert result.status == "success", result.error
    assert result.row_count == 1
    assert result.columns == ["product_count"]
    assert int(result.rows[0]["product_count"]) >= 1


@pytest.mark.integration
def test_readonly_session_rejects_writes() -> None:
    with pytest.raises(SQLAlchemyError):
        with reader_engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO analytics.products "
                    "(product_id, created_at, product_name) "
                    "VALUES (-999, NOW(), 'should_fail')"
                )
            )
            conn.commit()
