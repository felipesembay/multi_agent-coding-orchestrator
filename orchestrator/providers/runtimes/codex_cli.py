"""Codex CLI legacy read-only reviewer."""
from ..base import Capability, CapabilityManifest, CommandRuntime, InvocationRequest, InvocationResult


class CodexCliRuntime(CommandRuntime):
    provider = 'codex_cli'
    executable = 'codex'
    manifest = CapabilityManifest(
        adapter='codex_cli', kind='agent_runtime',
        capabilities={Capability.TEXT, Capability.REVIEW, Capability.REPO_CONTEXT},
        permission_modes=['read_only'], auth_modes=['cli_managed'],
        billing_mode='unknown', usage_source='none', verified=False,
        environment_variables={'CODEX_HOME'},
    )

    def _invoke(self, req: InvocationRequest) -> InvocationResult:
        if req.permission != 'read_only':
            raise ValueError('Legacy Codex runtime requires read_only')
        text = self._run(
            ['codex', 'exec', '--sandbox', 'read-only', req.prompt], req,
        )
        return InvocationResult(text=text)
