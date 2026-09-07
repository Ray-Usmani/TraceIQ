"""Background runner that projects LangGraph progress into the run registry."""

from __future__ import annotations

import logging
from typing import Any

from app.agent.graph import get_graph
from app.agent.state import AnalysisState
from app.config import get_settings
from app.services.run_registry import RunRegistry

logger = logging.getLogger(__name__)

settings = get_settings()
run_registry = RunRegistry(
    max_terminal_runs=settings.analysis_run_cache_size,
    max_active_runs=settings.analysis_max_active_runs,
)


def run_investigation(
    run_id: str,
    question: str,
    *,
    registry: RunRegistry = run_registry,
    graph: Any | None = None,
) -> None:
    """Execute a graph synchronously and publish each values-mode snapshot."""
    registry.set_status(run_id, "running")
    initial_state: AnalysisState = {
        "run_id": run_id,
        "user_question": question,
        "status": "running",
        "current_step_index": 0,
        "current_step": None,
        "completed_steps": [],
        "evidence": [],
        "errors": [],
    }

    try:
        compiled = graph or get_graph()
        for state in compiled.stream(initial_state, stream_mode="values"):
            registry.update_from_state(run_id, state)
    except Exception as exc:
        logger.exception("Investigation run failed", extra={"run_id": run_id})
        registry.mark_failed(run_id, f"Investigation failed: {exc}")
