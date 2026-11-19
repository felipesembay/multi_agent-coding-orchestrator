"""V2-WF-006: Antigravity as reviewer with validated JSON output and fixtures."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from orchestrator import core
from orchestrator.providers import bindings, registry
from orchestrator.providers.base import Capability, InvocationRequest
from orchestrator.providers.runtimes.antigravity import AntigravityRuntime
from orchestrator.workflows.compiler import compile_workflow


def _envelope(response_text: str, *, status: str = "SUCCESS", denied_actions: list | None = None) -> str:
    return json.dumps(
        {
            "status": status,
            "response": response_text,
            "denied_actions": denied_actions or [],
        }
    )


def test_antigravity_reviewer_returns_validated_structured_output() -> None:
    review_json = {
        "approved": True,
        "findings": [],
        "test_suggestions": ["Add edge-case coverage for empty input"],
    }
    runner = Mock(return_value=_envelope(json.dumps(review_json)))
    runtime = AntigravityRuntime(runner)

    assert Capability.REVIEW in runtime.manifest.capabilities
    assert Capability.STRUCTURED_OUTPUT in runtime.manifest.capabilities

    res = runtime.invoke(
        InvocationRequest(
            role="reviewer",
            prompt="Review current worktree",
            cwd="/tmp/wt",
            model="gemini-4-argon-medium",
            permission="read_only",
        )
    )
    assert res.structured == review_json
    assert runner.call_args.args[0] == [
        "agy",
        "--print",
        "Review current worktree",
        "--model",
        "gemini-4-argon-medium",
        "--mode",
        "plan",
        "--output-format",
        "json",
    ]


def test_antigravity_reviewer_extracts_fenced_json_block() -> None:
    fenced = 'Review complete:\n```json\n{"approved": false, "findings": ["Missing input check"], "test_suggestions": []}\n```'
    runner = Mock(return_value=_envelope(fenced))
    runtime = AntigravityRuntime(runner)
    res = runtime.invoke(
        InvocationRequest(
            role="reviewer",
            prompt="Review current worktree",
            cwd="/tmp/wt",
            permission="read_only",
        )
    )
    assert res.structured == {
        "approved": False,
        "findings": ["Missing input check"],
        "test_suggestions": [],
    }


@pytest.mark.parametrize(
    "bad_response,expected_match",
    [
        ("Looks good to me! Approved.", "not valid JSON"),
        ('["not", "an", "object"]', "must be a JSON object"),
        ('{"approved": "yes", "findings": []}', "boolean approved"),
        ('{"approved": 1, "findings": []}', "boolean approved"),
        ('{"approved": true}', "string list findings"),
        ('{"approved": true, "findings": "none"}', "string list findings"),
        ('{"approved": true, "findings": [123]}', "string list findings"),
        (
            '{"approved": true, "findings": [], "test_suggestions": "not-a-list"}',
            "test_suggestions must be a string list",
        ),
        (
            '{"approved": true, "findings": [], "test_suggestions": [42]}',
            "test_suggestions must be a string list",
        ),
    ],
)
def test_antigravity_reviewer_rejects_free_text_or_invalid_schema(
    bad_response: str, expected_match: str
) -> None:
    runner = Mock(return_value=_envelope(bad_response))
    runtime = AntigravityRuntime(runner)
    with pytest.raises(RuntimeError, match=expected_match):
        runtime.invoke(
            InvocationRequest(
                role="reviewer",
                prompt="Review current worktree",
                cwd="/tmp/wt",
                permission="read_only",
            )
        )


def test_antigravity_reviewer_integrates_with_core_review_and_records_agent_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ORCH_DB", str(tmp_path / "events.db"))
    monkeypatch.setenv("ORCH_TEST_COMMAND", "pytest -q")

    config = bindings.legacy_bindings({}).model_dump()
    config["reviewer"] = {
        "adapter": "antigravity",
        "model": "gemini-4-argon-medium",
        "permission": "read_only",
    }

    review_payload = {
        "approved": True,
        "findings": [],
        "test_suggestions": ["Verify negative numbers"],
    }

    def fake_run_command(argv: list[str], cwd: str, timeout: int = 600, env: dict | None = None) -> str:
        if argv[0] == "agy":
            assert "--mode" in argv and argv[argv.index("--mode") + 1] == "plan"
            return _envelope(json.dumps(review_payload))
        return "1 passed"

    monkeypatch.setattr(core, "run_command", fake_run_command)

    state: core.State = {
        "run_id": "run-0123456789ab",
        "worktree": str(tmp_path),
        "task_index": 0,
        "plan": {"tasks": [{"id": "T1", "title": "Task 1", "instructions": "do it", "acceptance": ["ok"]}]},
        "bindings": config,
    }
    out = core.review(state)
    assert out["review"]["approved"] is True
    assert out["review"]["findings"] == []
    assert out["review"]["test_suggestions"] == ["Verify negative numbers"]
    assert out["review"]["test_result"]["passed"] is True

    events = core._load_events(state["run_id"])
    agent_calls = [p for stage, p in events if stage == "agent_call"]
    assert len(agent_calls) == 1
    assert agent_calls[0]["provider"] == "antigravity"
    assert agent_calls[0]["role"] == "reviewer"
