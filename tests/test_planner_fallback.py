from unittest.mock import patch

import pytest

from orchestrator.core import coding_agent


def test_claude_is_primary_planner():
    with patch("orchestrator.core.claude", return_value='{"tasks": []}') as claude:
        with patch("orchestrator.core.antigravity") as agy:
            result = coding_agent("Plan task", "/tmp", "planner")

    assert result == '{"tasks": []}'
    claude.assert_called_once()
    agy.assert_not_called()


@pytest.mark.parametrize("error", [
    "claude exited 1: rate limit exceeded",
    "claude exited 1: usage limit reached",
    "claude exited 1: quota exceeded",
])
def test_antigravity_fallback_on_quota(error):
    with patch("orchestrator.core.claude", side_effect=RuntimeError(error)):
        with patch(
            "orchestrator.core.antigravity",
            return_value='{"tasks": []}',
        ) as agy:
            result = coding_agent("Plan task", "/tmp", "planner")

    assert result == '{"tasks": []}'
    assert agy.call_count == 1
    assert agy.call_args.kwargs["mode"] == "plan"


def test_no_fallback_on_unrelated_error():
    with patch(
        "orchestrator.core.claude",
        side_effect=RuntimeError("claude exited 1: authentication failed"),
    ):
        with patch("orchestrator.core.antigravity") as agy:
            with pytest.raises(RuntimeError, match="authentication failed"):
                coding_agent("Plan task", "/tmp", "planner")

    agy.assert_not_called()


def test_no_planner_fallback_for_implementer(monkeypatch):
    monkeypatch.setenv("ORCH_IMPLEMENTER", "claude")
    with patch(
        "orchestrator.core.claude",
        side_effect=RuntimeError("claude exited 1: rate limit exceeded"),
    ):
        with patch("orchestrator.core.antigravity") as agy:
            with pytest.raises(RuntimeError, match="rate limit"):
                coding_agent("Implement task", "/tmp", "implementer")

    agy.assert_not_called()


def test_fallback_event_is_persisted(monkeypatch, tmp_path):
    import json

    from orchestrator.core import db

    database = tmp_path / "events.db"
    monkeypatch.setenv("ORCH_DB", str(database))
    monkeypatch.setenv("ORCH_PLANNER", "claude")

    state = {
        "run_id": "run-fallback-test",
        "worktree": str(tmp_path),
    }

    with patch(
        "orchestrator.core.claude",
        side_effect=RuntimeError("claude exited 1: usage limit reached"),
    ):
        with patch(
            "orchestrator.core.antigravity",
            return_value='{"tasks": []}',
        ) as agy:
            result = coding_agent(
                "Plan task",
                str(tmp_path),
                "planner",
                state=state,
            )

    assert result == '{"tasks": []}'
    agy.assert_called_once()

    with db(str(database)) as conn:
        rows = conn.execute(
            "SELECT run_id, stage, payload FROM events"
        ).fetchall()

    assert len(rows) == 1

    run_id, stage, payload = rows[0]
    data = json.loads(payload)

    assert run_id == "run-fallback-test"
    assert stage == "agent_fallback"
    assert data == {
        "role": "planner",
        "primary": "claude",
        "fallback": "antigravity",
        "reason": "usage_limit",
    }
