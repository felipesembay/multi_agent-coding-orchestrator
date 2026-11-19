from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph


class _CheckpointState(TypedDict):
    run_id: str
    step_count: int
    steps: list[str]


def test_python_target_runtime_is_at_least_312() -> None:
    """V2-F0-005: Target Python runtime is 3.12+ per operator decision Q3."""
    assert sys.version_info >= (3, 12), f"Expected Python >= 3.12, got {sys.version}"


def test_sqlite_saver_state_graph_round_trip(tmp_path: Path) -> None:
    """V2-F0-005: Verify SqliteSaver import and minimal StateGraph checkpoint round-trip."""
    checkpoint_db = tmp_path / "checkpoints.db"

    def step_a(state: _CheckpointState) -> _CheckpointState:
        return {
            "run_id": state["run_id"],
            "step_count": state["step_count"] + 1,
            "steps": [*state["steps"], "step_a"],
        }

    def step_b(state: _CheckpointState) -> _CheckpointState:
        return {
            "run_id": state["run_id"],
            "step_count": state["step_count"] + 1,
            "steps": [*state["steps"], "step_b"],
        }

    builder = StateGraph(_CheckpointState)
    builder.add_node("step_a", step_a)
    builder.add_node("step_b", step_b)
    builder.add_edge(START, "step_a")
    builder.add_edge("step_a", "step_b")
    builder.add_edge("step_b", END)

    config = {"configurable": {"thread_id": "run-f0-005-roundtrip"}}

    with SqliteSaver.from_conn_string(str(checkpoint_db)) as saver:
        graph = builder.compile(checkpointer=saver)
        result = graph.invoke(
            {"run_id": "run-f0-005-roundtrip", "step_count": 0, "steps": []},
            config=config,
        )
        assert result == {
            "run_id": "run-f0-005-roundtrip",
            "step_count": 2,
            "steps": ["step_a", "step_b"],
        }

    # Reopen from disk to prove durable SQLite round-trip
    with SqliteSaver.from_conn_string(str(checkpoint_db)) as reopened_saver:
        reopened_graph = builder.compile(checkpointer=reopened_saver)
        snapshot = reopened_graph.get_state(config)
        assert snapshot.values == {
            "run_id": "run-f0-005-roundtrip",
            "step_count": 2,
            "steps": ["step_a", "step_b"],
        }
        history = list(reopened_graph.get_state_history(config))
        assert len(history) >= 3
