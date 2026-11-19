"""Codex CLI runtime with mechanism-enforced role permissions (SEC-004 / WF-005)."""
from ...policy.roles import build_codex_argv
from ..base import Capability, CapabilityManifest, CommandRuntime, InvocationRequest, InvocationResult


class CodexCliRuntime(CommandRuntime):
    provider = 'codex_cli'
    executable = 'codex'
    manifest = CapabilityManifest(
        adapter='codex_cli', kind='agent_runtime',
        capabilities={Capability.TEXT, Capability.CODE_EDIT, Capability.CODE_EXEC, Capability.REVIEW, Capability.REPO_CONTEXT},
        permission_modes=['read_only', 'workspace_write'], auth_modes=['cli_managed'],
        billing_mode='unknown', usage_source='none', verified=False,
        environment_variables={'CODEX_HOME'},
    )

    def _invoke(self, req: InvocationRequest) -> InvocationResult:
        argv = build_codex_argv(
            role=req.role,
            permission=req.permission,
            prompt=req.prompt,
            supported_modes=self.manifest.permission_modes,
        )
        text = self._run(argv, req)
        return InvocationResult(text=text)
