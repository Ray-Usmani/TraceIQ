"""Thread-safe, process-local storage for Phase 3 run snapshots."""

from __future__ import annotations

from collections import OrderedDict
from datetime import UTC, datetime
from threading import RLock

from app.agent.state import AnalysisRunSnapshot, AnalysisState, RunStatus

_ACTIVE_STATUSES = {"queued", "running"}
_TERMINAL_STATUSES = {
    "needs_clarification",
    "completed",
    "completed_with_errors",
    "failed",
}


class RunCapacityError(RuntimeError):
    """Raised when the process-local active-run limit has been reached."""


class RunNotFoundError(KeyError):
    """Raised when a run is unknown or has been evicted."""


class RunRegistry:
    """Bounded registry that returns defensive copies of every snapshot."""

    def __init__(self, *, max_terminal_runs: int = 100, max_active_runs: int = 4):
        if max_terminal_runs < 1 or max_active_runs < 1:
            raise ValueError("Run registry limits must be positive")
        self.max_terminal_runs = max_terminal_runs
        self.max_active_runs = max_active_runs
        self._runs: OrderedDict[str, AnalysisRunSnapshot] = OrderedDict()
        self._lock = RLock()

    def create(self, run_id: str, question: str) -> AnalysisRunSnapshot:
        """Create a queued run if active capacity is available."""
        with self._lock:
            active = sum(
                snapshot.status in _ACTIVE_STATUSES
                for snapshot in self._runs.values()
            )
            if active >= self.max_active_runs:
                raise RunCapacityError("Too many analysis runs are currently active")
            snapshot = AnalysisRunSnapshot(
                run_id=run_id,
                question=question,
                status="queued",
            )
            self._runs[run_id] = snapshot
            return snapshot.model_copy(deep=True)

    def get(self, run_id: str) -> AnalysisRunSnapshot:
        """Return a defensive copy so callers cannot mutate registry state."""
        with self._lock:
            snapshot = self._runs.get(run_id)
            if snapshot is None:
                raise RunNotFoundError(run_id)
            return snapshot.model_copy(deep=True)

    def set_status(self, run_id: str, status: RunStatus) -> AnalysisRunSnapshot:
        """Change only lifecycle status while preserving accumulated results."""
        with self._lock:
            current = self._require(run_id)
            updated = current.model_copy(
                update={"status": status, "updated_at": datetime.now(UTC)},
                deep=True,
            )
            self._runs[run_id] = updated
            self._evict_terminal_runs()
            return updated.model_copy(deep=True)

    def update_from_state(
        self,
        run_id: str,
        state: AnalysisState,
    ) -> AnalysisRunSnapshot:
        """Replace a snapshot with the latest complete graph-state projection."""
        with self._lock:
            current = self._require(run_id)
            updated = AnalysisRunSnapshot(
                run_id=run_id,
                question=state.get("user_question", current.question),
                status=state.get("status", current.status),
                intake=state.get("intake", current.intake),
                plan=state.get("investigation_plan", current.plan),
                current_step=state.get("current_step", current.current_step),
                completed_steps=state.get(
                    "completed_steps", current.completed_steps
                ),
                evidence=state.get("evidence", current.evidence),
                errors=state.get("errors", current.errors),
                created_at=current.created_at,
                updated_at=datetime.now(UTC),
            )
            self._runs[run_id] = updated
            self._evict_terminal_runs()
            return updated.model_copy(deep=True)

    def mark_failed(self, run_id: str, error: str) -> AnalysisRunSnapshot:
        """Record an unhandled graph failure as a terminal run."""
        with self._lock:
            current = self._require(run_id)
            updated = current.model_copy(
                update={
                    "status": "failed",
                    "current_step": None,
                    "errors": [*current.errors, error],
                    "updated_at": datetime.now(UTC),
                },
                deep=True,
            )
            self._runs[run_id] = updated
            self._evict_terminal_runs()
            return updated.model_copy(deep=True)

    def clear(self) -> None:
        """Clear all process-local state (primarily for tests)."""
        with self._lock:
            self._runs.clear()

    def _require(self, run_id: str) -> AnalysisRunSnapshot:
        snapshot = self._runs.get(run_id)
        if snapshot is None:
            raise RunNotFoundError(run_id)
        return snapshot

    def _evict_terminal_runs(self) -> None:
        terminal_ids = [
            run_id
            for run_id, snapshot in self._runs.items()
            if snapshot.status in _TERMINAL_STATUSES
        ]
        excess = len(terminal_ids) - self.max_terminal_runs
        for run_id in terminal_ids[: max(excess, 0)]:
            del self._runs[run_id]
