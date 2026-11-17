"""Codex CLI legacy read-only reviewer."""
from ..base import CommandRuntime, InvocationRequest, InvocationResult


class CodexCliRuntime(CommandRuntime):
    def invoke(self, req: InvocationRequest) -> InvocationResult:
        if req.permission != 'read_only':
            raise ValueError('Legacy Codex runtime requires read_only')
        text = self._run(
            ['codex', 'exec', '--sandbox', 'read-only', req.prompt], req,
        )
        return InvocationResult(text=text)
