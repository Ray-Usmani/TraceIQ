"""SQL safety validator unit tests (no database / OpenAI required)."""

from __future__ import annotations

import pytest

from app.agent.tools.sql_validator import validate


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT website_session_id FROM analytics.website_sessions LIMIT 10",
        "SELECT COUNT(*) AS n FROM analytics.orders",
        """
        WITH monthly AS (
            SELECT DATE_TRUNC('month', created_at) AS month, COUNT(*) AS sessions
            FROM analytics.website_sessions
            GROUP BY 1
        )
        SELECT * FROM monthly ORDER BY month
        """,
        (
            "SELECT o.order_id, p.product_name FROM analytics.orders o "
            "JOIN analytics.products p ON o.primary_product_id = p.product_id LIMIT 5"
        ),
    ],
)
def test_allows_select_and_cte(sql: str) -> None:
    result = validate(sql)
    assert result.valid, result.error
    assert result.statement_type == "Select"


@pytest.mark.parametrize(
    "sql,fragment",
    [
        ("INSERT INTO analytics.orders (order_id) VALUES (1)", "Insert"),
        ("UPDATE analytics.orders SET price_usd = 0", "Update"),
        ("DELETE FROM analytics.orders", "Delete"),
        ("DROP TABLE analytics.orders", "Drop"),
        ("ALTER TABLE analytics.orders ADD COLUMN x INT", "Alter"),
        ("TRUNCATE analytics.orders", "Forbidden"),
        ("CREATE TABLE analytics.evil (id INT)", "Create"),
        ("GRANT SELECT ON analytics.orders TO public", "Grant"),
("COPY analytics.orders TO '/tmp/out.csv'", "Copy"),
            ("SELECT 1; DROP TABLE analytics.orders;", "Multiple"),
        (
            "SELECT order_id INTO analytics.new_orders FROM analytics.orders",
            "INTO",
        ),
    ],
)
def test_rejects_unsafe_sql(sql: str, fragment: str) -> None:
    result = validate(sql)
    assert not result.valid, f"Expected rejection for: {sql}"
    assert result.error is not None
    assert fragment.lower() in result.error.lower()


def test_rejects_empty() -> None:
    result = validate("   ")
    assert not result.valid


def test_warns_missing_schema_prefix() -> None:
    result = validate("SELECT * FROM website_sessions LIMIT 1")
    assert result.valid
    assert any("analytics" in w for w in result.warnings)
