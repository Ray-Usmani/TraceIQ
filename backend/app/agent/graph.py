"""LangGraph definition for the Phase 3 SQL investigation workflow."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Any, cast

from langgraph.graph import END, START, StateGraph

from app.agent.nodes.intake import (
    intake_node,
    load_context_node,
    route_after_intake,
)
from app.agent.nodes.planner import planner_node
from app.agent.nodes.router import (
    execute_sql_node,
    finalize_node,
    route_current_step,
    select_step_node,
)
from app.agent.state import AnalysisState
from app.agent.tools.sql_tool import run_sql_analysis
from app.services.evidence import SqlArtifact

StateNode = Callable[[AnalysisState], Any]
SqlRunner = Callable[..., SqlArtifact]


def build_graph(
    *,
    intake: StateNode = intake_node,
    context_loader: StateNode = load_context_node,
    planner: StateNode = planner_node,
    sql_runner: SqlRunner = run_sql_analysis,
) -> Any:
    """Build and compile the bounded, sequential investigation graph."""
    # LangGraph's overloaded node protocol does not model injected callables well.
    graph = cast(Any, StateGraph(AnalysisState))
    graph.add_node("intake", intake)
    graph.add_node("load_context", context_loader)
    graph.add_node("planner", planner)
    graph.add_node("select_step", select_step_node)
    graph.add_node(
        "execute_sql",
        lambda state: execute_sql_node(state, sql_runner=sql_runner),
    )
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "intake")
    graph.add_conditional_edges(
        "intake",
        route_after_intake,
        {"clarify": END, "continue": "load_context"},
    )
    graph.add_edge("load_context", "planner")
    graph.add_edge("planner", "select_step")
    graph.add_conditional_edges(
        "select_step",
        route_current_step,
        {"sql": "execute_sql", "finalize": "finalize"},
    )
    graph.add_edge("execute_sql", "select_step")
    graph.add_edge("finalize", END)
    return graph.compile()


@lru_cache
def get_graph() -> Any:
    """Return the production graph compiled once per backend process."""
    return build_graph()
