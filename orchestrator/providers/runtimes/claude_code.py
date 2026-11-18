"""Claude Code legacy command; read-only planning is a separate security task."""
from ..base import Capability, CapabilityManifest, CommandRuntime, InvocationRequest, InvocationResult


class ClaudeCodeRuntime(CommandRuntime):
    provider = 'claude_code'
    executable = 'claude'
    manifest = CapabilityManifest(
        adapter='claude_code', kind='agent_runtime',
        capabilities={Capability.TEXT, Capability.PLANNING, Capability.CODE_EDIT, Capability.REPO_CONTEXT},
        permission_modes=['workspace_write'], auth_modes=['cli_managed'],
        billing_mode='unknown', usage_source='none', verified=False,
        environment_variables={'CLAUDE_CONFIG_DIR'},
    )

    def _invoke(self, req: InvocationRequest) -> InvocationResult:
        if req.permission != 'workspace_write':
            raise ValueError('Legacy Claude runtime requires workspace_write')
        text = self._run(
            ['claude', '-p', '--permission-mode', 'acceptEdits', req.prompt], req,
        )
        return InvocationResult(text=text)
