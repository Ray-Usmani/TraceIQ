"""Tests for bounded, defensive in-memory run storage."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.run_registry import (
    RunCapacityError,
    RunNotFoundError,
    RunRegistry,
)


def test_registry_enforces_active_capacity() -> None:
    registry = RunRegistry(max_terminal_runs=2, max_active_runs=1)
    registry.create("run_1", "Question one")

    with pytest.raises(RunCapacityError):
        registry.create("run_2", "Question two")


def test_registry_capacity_is_atomic_across_threads() -> None:
    registry = RunRegistry(max_terminal_runs=2, max_active_runs=4)

    def create(index: int) -> bool:
        try:
            registry.create(f"run_{index}", "Question")
        except RunCapacityError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(create, range(8)))

    assert results.count(True) == 4
    assert results.count(False) == 4


def test_registry_returns_defensive_snapshots() -> None:
    registry = RunRegistry()
    registry.create("run_1", "Question")

    snapshot = registry.get("run_1")
    snapshot.errors.append("caller mutation")

    assert registry.get("run_1").errors == []


def test_registry_evicts_oldest_terminal_run_only() -> None:
    registry = RunRegistry(max_terminal_runs=2, max_active_runs=2)
    for index in range(3):
        run_id = f"run_{index}"
        registry.create(run_id, f"Question {index}")
        registry.set_status(run_id, "completed")

    with pytest.raises(RunNotFoundError):
        registry.get("run_0")
    assert registry.get("run_1").status == "completed"
    assert registry.get("run_2").status == "completed"


def test_mark_failed_preserves_existing_errors() -> None:
    registry = RunRegistry()
    registry.create("run_1", "Question")
    registry.update_from_state(
        "run_1",
        {
            "user_question": "Question",
            "status": "running",
            "errors": ["step warning"],
        },
    )

    result = registry.mark_failed("run_1", "graph failed")

    assert result.status == "failed"
    assert result.errors == ["step warning", "graph failed"]
