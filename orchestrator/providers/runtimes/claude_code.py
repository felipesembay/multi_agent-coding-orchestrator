"""Claude Code legacy command; read-only planning is a separate security task."""
from ..base import CommandRuntime, InvocationRequest, InvocationResult


class ClaudeCodeRuntime(CommandRuntime):
    provider = 'claude_code'

    def _invoke(self, req: InvocationRequest) -> InvocationResult:
        if req.permission != 'workspace_write':
            raise ValueError('Legacy Claude runtime requires workspace_write')
        text = self._run(
            ['claude', '-p', '--permission-mode', 'acceptEdits', req.prompt], req,
        )
        return InvocationResult(text=text)
