"""PostgreSQL-backed Phase 3 graph smoke test with deterministic LLM stubs."""

from __future__ import annotations

import pytest

from app.agent.graph import build_graph
from app.agent.state import IntakeResult, InvestigationPlan, InvestigationStep
from app.agent.tools import sql_tool


@pytest.mark.integration
def test_graph_executes_two_real_readonly_queries(monkeypatch: object) -> None:
    def intake(_state: object) -> dict[str, object]:
        return {
            "intake": IntakeResult(
                intent="descriptive",
                relevant_tables=["products", "orders"],
                relevant_metrics=["orders"],
            ),
            "status": "running",
        }

    def context(_state: object) -> dict[str, object]:
        return {"schema_context": "schema", "metric_context": "metrics"}

    def planner(_state: object) -> dict[str, object]:
        return {
            "investigation_plan": InvestigationPlan(
                objective="Count products and orders",
                steps=[
                    InvestigationStep(
                        id="step_1",
                        question="Count products",
                        purpose="Verify catalog",
                    ),
                    InvestigationStep(
                        id="step_2",
                        question="Count orders",
                        purpose="Verify orders",
                    ),
                ],
            ),
            "current_step_index": 0,
        }

    def fake_sql_llm(prompt: str) -> dict[str, object]:
        if "Count products" in prompt:
            return {
                "sql": "SELECT COUNT(*) AS product_count FROM analytics.products",
                "reason": "Count catalog rows",
                "expected_columns": ["product_count"],
            }
        return {
            "sql": "SELECT COUNT(*) AS order_count FROM analytics.orders",
            "reason": "Count order rows",
            "expected_columns": ["order_count"],
        }

    monkeypatch.setattr(sql_tool, "_call_llm", fake_sql_llm)
    graph = build_graph(intake=intake, context_loader=context, planner=planner)

    result = graph.invoke(
        {
            "run_id": "integration",
            "user_question": "Count products and orders",
            "status": "running",
            "completed_steps": [],
            "evidence": [],
            "errors": [],
        }
    )

    assert result["status"] == "completed"
    assert len(result["evidence"]) == 2
    assert [item.step_id for item in result["evidence"]] == ["step_1", "step_2"]
    assert all(item.row_count == 1 for item in result["evidence"])
