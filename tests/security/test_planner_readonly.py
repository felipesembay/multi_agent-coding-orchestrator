"""V2-SEC-003: Claude Planner uses read-only --permission-mode plan and returns extractable JSON."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from orchestrator import core
from orchestrator.providers import bindings, registry
from orchestrator.providers.base import InvocationRequest
from orchestrator.providers.runtimes.claude_code import ClaudeCodeRuntime


def test_claude_runtime_maps_read_only_to_plan_and_workspace_write_to_accept_edits() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: str, timeout: int, env: dict | None = None) -> str:
        calls.append(argv)
        return '{"tasks":[{"id":"T1","title":"Plan","instructions":"Read only","acceptance":["ok"]}]}'

    runtime = ClaudeCodeRuntime(runner)
    res_plan = runtime.invoke(
        InvocationRequest(role="planner", prompt="create plan", cwd="/tmp/wt", permission="read_only")
    )
    res_impl = runtime.invoke(
        InvocationRequest(role="implementer", prompt="edit code", cwd="/tmp/wt", permission="workspace_write")
    )

    assert calls[0] == ["claude", "-p", "--permission-mode", "plan", "create plan"]
    assert calls[1] == [
        "claude",
        "-p",
        "--permission-mode",
        "acceptEdits",
        "--disallowedTools",
        "Bash",
        "edit code",
    ]
    assert core.extract_json(res_plan.text)["tasks"][0]["id"] == "T1"
    assert res_impl.text.startswith("{")


def test_planner_rejects_workspace_write_permission_for_claude() -> None:
    config = bindings.legacy_bindings({}).model_dump()
    assert config["planner"]["adapter"] == "claude_code"
    assert config["planner"]["permission"] == "read_only"
    config["planner"]["permission"] = "workspace_write"
    with pytest.raises(ValueError, match="planner requires read_only permission"):
        bindings.validate_bindings(
            bindings.AgentBindings.model_validate(config),
            registry.ProviderRegistry(),
        )


def test_core_plan_with_claude_uses_plan_mode_and_extracts_fenced_or_raw_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ORCH_DB", str(tmp_path / "events.db"))
    for key in ("ORCH_PLANNER", "ORCH_IMPLEMENTER", "ORCH_PLANNER_MODEL", "AGENT_TIMEOUT"):
        monkeypatch.delenv(key, raising=False)

    worktree = tmp_path / "wt"
    worktree.mkdir()
    sentinel_file = worktree / "existing.py"
    sentinel_file.write_text("x = 1\n", encoding="utf-8")

    plan_payload = {
        "tasks": [
            {
                "id": "T1",
                "title": "Add validation",
                "instructions": "Inspect and validate inputs",
                "acceptance": ["Tests pass"],
                "tests": ["pytest -q"],
            }
        ]
    }
    fenced_response = f"Here is the plan:\n```json\n{json.dumps(plan_payload)}\n```\n"

    monkeypatch.setattr(core.shutil, "which", lambda name, **kwargs: "/mock/" + name)
    runner = Mock(return_value=SimpleNamespace(returncode=0, stdout=fenced_response, stderr=""))
    monkeypatch.setattr(core.subprocess, "run", runner)

    state: core.State = {
        "run_id": "run-0123456789ab",
        "repo": str(tmp_path),
        "worktree": str(worktree),
        "scope": "Implement input validation",
        "managed": True,
    }
    out = core.plan(state)

    assert runner.call_count == 1
    called_argv = runner.call_args.args[0]
    assert called_argv[:4] == ["claude", "-p", "--permission-mode", "plan"]
    assert "acceptEdits" not in called_argv
    assert out["plan"] == plan_payload
    assert sentinel_file.read_text(encoding="utf-8") == "x = 1\n"
    assert list(worktree.iterdir()) == [sentinel_file]
