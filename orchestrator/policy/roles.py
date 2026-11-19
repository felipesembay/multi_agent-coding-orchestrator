"""Mechanism-enforced role permission matrix and CLI argv builder (V2-SEC-004).

Prompt text is not a security control. Every adapter invocation validates the
(role, permission) pair against the authoritative role matrix and constructs
CLI flags deterministically.
"""
from __future__ import annotations

from typing import Literal, Optional

PermissionMode = Literal["read_only", "workspace_write"]

ROLE_ALLOWED_PERMISSIONS: dict[str, frozenset[PermissionMode]] = {
    "planner": frozenset({"read_only"}),
    "reviewer": frozenset({"read_only"}),
    "implementer": frozenset({"workspace_write"}),
    "documenter": frozenset({"read_only", "workspace_write"}),
    # Standalone direct facade/contract calls without an orchestration role
    "legacy": frozenset({"read_only", "workspace_write"}),
}


class RolePermissionError(ValueError):
    """Raised when a role/permission combination or adapter mode is disallowed."""


def validate_role_permission(
    role: str,
    permission: str,
    *,
    supported_modes: Optional[list[str] | set[str] | tuple[str, ...]] = None,
) -> PermissionMode:
    if permission not in ("read_only", "workspace_write"):
        raise RolePermissionError(f"Unsupported permission mode: {permission}")
    allowed = ROLE_ALLOWED_PERMISSIONS.get(role)
    if allowed is None:
        raise RolePermissionError(f"Unknown agent role: {role}")
    if permission not in allowed:
        raise RolePermissionError(
            f"Role '{role}' is not permitted to run with '{permission}'"
        )
    if supported_modes is not None and permission not in supported_modes:
        raise RolePermissionError(
            f"Adapter does not support permission '{permission}' for role '{role}'"
        )
    return permission  # type: ignore[return-value]


def build_claude_argv(
    *,
    role: str,
    permission: str,
    prompt: str,
    supported_modes: Optional[list[str]] = None,
) -> list[str]:
    perm = validate_role_permission(role, permission, supported_modes=supported_modes)
    if perm == "read_only":
        return ["claude", "-p", "--permission-mode", "plan", prompt]
    return [
        "claude",
        "-p",
        "--permission-mode",
        "acceptEdits",
        "--disallowedTools",
        "Bash",
        prompt,
    ]


def build_codex_argv(
    *,
    role: str,
    permission: str,
    prompt: str,
    supported_modes: Optional[list[str]] = None,
) -> list[str]:
    perm = validate_role_permission(role, permission, supported_modes=supported_modes)
    sandbox = "read-only" if perm == "read_only" else "workspace-write"
    return ["codex", "exec", "--sandbox", sandbox, prompt]


def build_antigravity_argv(
    *,
    role: str,
    permission: str,
    prompt: str,
    model: Optional[str],
    supported_modes: Optional[list[str]] = None,
) -> list[str]:
    perm = validate_role_permission(role, permission, supported_modes=supported_modes)
    mode = "plan" if perm == "read_only" else "accept-edits"
    return [
        "agy",
        "--print",
        prompt,
        "--model",
        model,  # type: ignore[list-item]
        "--mode",
        mode,
        "--output-format",
        "json",
    ]
