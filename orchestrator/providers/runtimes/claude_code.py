"""Claude Code runtime with mechanism-enforced role permissions (SEC-003/SEC-004)."""
from ...policy.roles import build_claude_argv
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
        argv = build_claude_argv(
            role=req.role,
            permission=req.permission,
            prompt=req.prompt,
            supported_modes=self.manifest.permission_modes,
        )
        text = self._run(argv, req)
        return InvocationResult(text=text)
