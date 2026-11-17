"""Minimal runtime contracts for the behavior-preserving legacy extraction.

Usage and invocation metadata belong to CORE-002; manifests, probing and plugin
registration belong to CORE-003. No capabilities are claimed as verified here.
"""
from __future__ import annotations

from typing import Literal, Optional, Protocol

from pydantic import BaseModel


class InvocationRequest(BaseModel):
    role: str = 'legacy'
    prompt: str
    cwd: str
    model: Optional[str] = None
    permission: Literal['read_only', 'workspace_write']
    output_schema: Optional[dict] = None
    timeout_s: int = 600
    # None retains the legacy inherited environment until SEC-002.
    env: Optional[dict[str, str]] = None


class InvocationResult(BaseModel):
    text: str


class AgentRuntime(Protocol):
    def invoke(self, req: InvocationRequest) -> InvocationResult: ...


class CommandRunner(Protocol):
    def __call__(self, argv: list[str], cwd: str, timeout: int,
                 env: Optional[dict] = None) -> str: ...


class CommandRuntime:
    """Share an injected process boundary without importing the workflow core."""

    def __init__(self, runner: CommandRunner):
        self._runner = runner

    def _run(self, argv: list[str], req: InvocationRequest) -> str:
        if req.env is None:
            return self._runner(argv, req.cwd, req.timeout_s)
        return self._runner(argv, req.cwd, req.timeout_s, env=req.env)
