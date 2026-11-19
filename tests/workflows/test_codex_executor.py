"""V2-WF-005: Codex CLI as executor with --sandbox workspace-write and Preset A integration."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from orchestrator import core
from orchestrator.policy.roles import RolePermissionError
from orchestrator.providers.base import Capability, InvocationRequest
from orchestrator.providers.registry import ProviderRegistry
from orchestrator.providers.runtimes.antigravity import AntigravityRuntime
from orchestrator.providers.runtimes.claude_code import ClaudeCodeRuntime
from orchestrator.providers.runtimes.codex_cli import CodexCliRuntime
from orchestrator.workflows.compiler import compile_workflow
from orchestrator.workflows.presets import get_preset, validate_preset


def test_codex_runtime_executes_implementer_with_workspace_write_sandbox() -> None:
    seen_argv: list[list[str]] = []

    def runner(argv: list[str], cwd: str, timeout: int, env: dict | None = None) -> str:
        seen_argv.append(argv)
        return "Implemented feature and updated files."

    runtime = CodexCliRuntime(runner)
    assert Capability.CODE_EDIT in runtime.manifest.capabilities
    assert Capability.CODE_EXEC in runtime.manifest.capabilities
    assert "workspace_write" in runtime.manifest.permission_modes

    result = runtime.invoke(
        InvocationRequest(
            role="implementer",
            prompt="Implement task T1",
            cwd="/tmp/worktree",
            permission="workspace_write",
            timeout_s=300,
        )
    )
    assert result.text == "Implemented feature and updated files."
    assert seen_argv == [["codex", "exec", "--sandbox", "workspace-write", "Implement task T1"]]


def test_codex_runtime_rejects_implementer_with_read_only_and_reviewer_with_workspace_write() -> None:
    runner = Mock(return_value="no")
    runtime = CodexCliRuntime(runner)
    with pytest.raises(RolePermissionError):
        runtime.invoke(
            InvocationRequest(role="implementer", prompt="task", cwd="/tmp/wt", permission="read_only")
        )
    with pytest.raises(RolePermissionError):
        runtime.invoke(
            InvocationRequest(role="reviewer", prompt="task", cwd="/tmp/wt", permission="workspace_write")
        )
    runner.assert_not_called()


def test_preset_a_implements_with_mocked_codex_cli_and_exact_flags(tmp_path: Path) -> None:
    calls: list[tuple[str, list[str]]] = []

    def make_runner(adapter: str):
        def _runner(argv: list[str], cwd: str, timeout: int, env: dict | None = None) -> str:
            calls.append((adapter, argv))
            if adapter == "claude_code":
                return json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "T1",
                                "title": "Add module",
                                "instructions": "Create feature.py",
                                "acceptance": ["passes tests"],
                            }
                        ]
                    }
                )
            if adapter == "codex_cli":
                (Path(cwd) / "feature.py").write_text("VALUE = 42\n", encoding="utf-8")
                return "Created feature.py with VALUE = 42"
            return json.dumps(
                {
                    "status": "SUCCESS",
                    "response": json.dumps({"approved": True, "findings": [], "test_suggestions": []}),
                }
            )

        return _runner

    runtimes = {
        "claude_code": ClaudeCodeRuntime(make_runner("claude_code")),
        "codex_cli": CodexCliRuntime(make_runner("codex_cli")),
        "antigravity": AntigravityRuntime(make_runner("antigravity")),
    }
    # Simulate verified capabilities on fake registry instances for workflow compilation
    for adapter, rt in runtimes.items():
        rt.manifest = rt.manifest.model_copy(
            update={
                "verified": True,
                "capabilities": set(rt.manifest.capabilities)
                | {Capability.STRUCTURED_OUTPUT, Capability.REVIEW},
            }
        )

    class VerifiedMockRegistry:
        def get(self, adapter: str):
            return runtimes[adapter]

    reg = VerifiedMockRegistry()
    selection = validate_preset("default-v2", registry=reg)
    worktree = tmp_path / "wt"
    worktree.mkdir()

    def execute_agent(context):
        rt = reg.get(context.adapter)
        req = InvocationRequest(
            role=context.step.role,
            prompt=f"run:{context.step.id}",
            cwd=str(worktree),
            model=context.binding.model,
            permission=context.binding.permission,
            timeout_s=120,
        )
        res = rt.invoke(req)
        if context.step.type in ("plan", "review"):
            return core.extract_json(res.text)
        return {"output": res.text}

    graph = compile_workflow(
        selection.definition,
        selection.bindings,
        provider_configs=selection.provider_configs,
        registry=reg,
        executors={
            "plan": execute_agent,
            "implement": execute_agent,
            "review": execute_agent,
            "test": lambda ctx: {"passed": (worktree / "feature.py").exists()},
        },
    )

    final_state = graph.invoke({})
    assert final_state["status"] == "ready_for_human_review"
    assert (worktree / "feature.py").read_text(encoding="utf-8") == "VALUE = 42\n"
    assert [adapter for adapter, _ in calls] == ["claude_code", "codex_cli", "antigravity"]
    assert calls[0][1] == ["claude", "-p", "--permission-mode", "plan", "run:plan"]
    assert calls[1][1] == ["codex", "exec", "--sandbox", "workspace-write", "run:impl"]
    assert calls[2][1][:3] == ["agy", "--print", "run:review"]
    assert "--mode" in calls[2][1] and calls[2][1][calls[2][1].index("--mode") + 1] == "plan"
