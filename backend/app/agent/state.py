"""LangGraph analysis state.

Stub for Phase 0. Full AnalysisState is defined in Phase 3.
"""

from typing import TypedDict


class AnalysisState(TypedDict, total=False):
    """Shared state for an investigation run."""

    run_id: str
    user_question: str
    status: str
