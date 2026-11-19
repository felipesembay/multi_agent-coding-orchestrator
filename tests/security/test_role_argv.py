"""V2-SEC-004: Role permission matrix enforced in adapter argv (SECURITY_GOVERNANCE CA3)."""
from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from orchestrator.policy.roles import (
    ROLE_ALLOWED_PERMISSIONS,
    RolePermissionError,
    build_antigravity_argv,
    build_claude_argv,
    build_codex_argv,
    validate_role_permission,
)
from orchestrator.providers.base import InvocationRequest
from orchestrator.providers.runtimes.antigravity import AntigravityRuntime
from orchestrator.providers.runtimes.claude_code import ClaudeCodeRuntime
from orchestrator.providers.runtimes.codex_cli import CodexCliRuntime

AGY_OK = json.dumps({"status": "SUCCESS", "response": "ok"})


@pytest.mark.parametrize(
    "role,permission,expected_argv",
    [
        ("planner", "read_only", ["claude", "-p", "--permission-mode", "plan", "prompt"]),
        ("reviewer", "read_only", ["claude", "-p", "--permission-mode", "plan", "prompt"]),
        ("documenter", "read_only", ["claude", "-p", "--permission-mode", "plan", "prompt"]),
        (
            "implementer",
            "workspace_write",
            ["claude", "-p", "--permission-mode", "acceptEdits", "--disallowedTools", "Bash", "prompt"],
        ),
        (
            "documenter",
            "workspace_write",
            ["claude", "-p", "--permission-mode", "acceptEdits", "--disallowedTools", "Bash", "prompt"],
        ),
    ],
)
def test_claude_role_argv_matrix(role: str, permission: str, expected_argv: list[str]) -> None:
    runner = Mock(return_value="ok")
    runtime = ClaudeCodeRuntime(runner)
    res = runtime.invoke(InvocationRequest(role=role, prompt="prompt", cwd="/tmp/wt", permission=permission))
    assert res.text == "ok"
    assert runner.call_count == 1
    assert runner.call_args.args[0] == expected_argv


@pytest.mark.parametrize(
    "role,permission,expected_argv",
    [
        (
            "planner",
            "read_only",
            ["agy", "--print", "prompt", "--model", "m1", "--mode", "plan", "--output-format", "json"],
        ),
        (
            "reviewer",
            "read_only",
            ["agy", "--print", "prompt", "--model", "m1", "--mode", "plan", "--output-format", "json"],
        ),
        (
            "documenter",
            "read_only",
            ["agy", "--print", "prompt", "--model", "m1", "--mode", "plan", "--output-format", "json"],
        ),
        (
            "implementer",
            "workspace_write",
            ["agy", "--print", "prompt", "--model", "m1", "--mode", "accept-edits", "--output-format", "json"],
        ),
        (
            "documenter",
            "workspace_write",
            ["agy", "--print", "prompt", "--model", "m1", "--mode", "accept-edits", "--output-format", "json"],
        ),
    ],
)
def test_antigravity_role_argv_matrix(role: str, permission: str, expected_argv: list[str]) -> None:
    runner = Mock(return_value=AGY_OK)
    runtime = AntigravityRuntime(runner)
    res = runtime.invoke(
        InvocationRequest(role=role, prompt="prompt", cwd="/tmp/wt", model="m1", permission=permission)
    )
    assert res.text == "ok"
    assert runner.call_count == 1
    assert runner.call_args.args[0] == expected_argv


@pytest.mark.parametrize(
    "role,permission,expected_argv",
    [
        ("planner", "read_only", ["codex", "exec", "--sandbox", "read-only", "prompt"]),
        ("reviewer", "read_only", ["codex", "exec", "--sandbox", "read-only", "prompt"]),
        ("documenter", "read_only", ["codex", "exec", "--sandbox", "read-only", "prompt"]),
    ],
)
def test_codex_readonly_role_argv_matrix(role: str, permission: str, expected_argv: list[str]) -> None:
    runner = Mock(return_value="ok")
    runtime = CodexCliRuntime(runner)
    res = runtime.invoke(InvocationRequest(role=role, prompt="prompt", cwd="/tmp/wt", permission=permission))
    assert res.text == "ok"
    assert runner.call_count == 1
    assert runner.call_args.args[0] == expected_argv


def test_codex_argv_builder_supports_workspace_write_for_implementer_when_enabled() -> None:
    argv = build_codex_argv(
        role="implementer",
        permission="workspace_write",
        prompt="implement feature",
        supported_modes=["read_only", "workspace_write"],
    )
    assert argv == ["codex", "exec", "--sandbox", "workspace-write", "implement feature"]


@pytest.mark.parametrize(
    "role,forbidden_permission",
    [
        ("planner", "workspace_write"),
        ("reviewer", "workspace_write"),
        ("implementer", "read_only"),
        ("unknown_role", "read_only"),
    ],
)
@pytest.mark.parametrize("runtime_cls", [ClaudeCodeRuntime, AntigravityRuntime])
def test_forbidden_role_permission_combinations_never_spawn_process(
    role: str, forbidden_permission: str, runtime_cls: type
) -> None:
    runner = Mock(return_value=AGY_OK)
    runtime = runtime_cls(runner)
    with pytest.raises(RolePermissionError):
        runtime.invoke(
            InvocationRequest(role=role, prompt="prompt", cwd="/tmp/wt", permission=forbidden_permission)
        )
    runner.assert_not_called()


def test_role_permission_matrix_is_exhaustive_and_blocks_escalation() -> None:
    assert ROLE_ALLOWED_PERMISSIONS["planner"] == frozenset({"read_only"})
    assert ROLE_ALLOWED_PERMISSIONS["reviewer"] == frozenset({"read_only"})
    assert ROLE_ALLOWED_PERMISSIONS["implementer"] == frozenset({"workspace_write"})
    assert ROLE_ALLOWED_PERMISSIONS["documenter"] == frozenset({"read_only", "workspace_write"})
    with pytest.raises(RolePermissionError):
        validate_role_permission("planner", "read_only", supported_modes=["workspace_write"])
    with pytest.raises(RolePermissionError):
        build_claude_argv(role="planner", permission="workspace_write", prompt="p")
    with pytest.raises(RolePermissionError):
        build_antigravity_argv(role="reviewer", permission="workspace_write", prompt="p", model="m")
