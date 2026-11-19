"""Claude Code runtime with read-only plan mode and workspace_write acceptEdits."""
from ..base import Capability, CapabilityManifest, CommandRuntime, InvocationRequest, InvocationResult


class ClaudeCodeRuntime(CommandRuntime):
    provider = 'claude_code'
    executable = 'claude'
    manifest = CapabilityManifest(
        adapter='claude_code', kind='agent_runtime',
        capabilities={Capability.TEXT, Capability.PLANNING, Capability.CODE_EDIT, Capability.REPO_CONTEXT},
        permission_modes=['read_only', 'workspace_write'], auth_modes=['cli_managed'],
        billing_mode='unknown', usage_source='none', verified=False,
        environment_variables={'CLAUDE_CONFIG_DIR'},
    )

    def _invoke(self, req: InvocationRequest) -> InvocationResult:
        if req.permission not in ('read_only', 'workspace_write'):
            raise ValueError(f'Unsupported Claude permission: {req.permission}')
        mode = 'plan' if req.permission == 'read_only' else 'acceptEdits'
        text = self._run(
            ['claude', '-p', '--permission-mode', mode, req.prompt], req,
        )
        return InvocationResult(text=text)
