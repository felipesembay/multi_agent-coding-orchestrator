"""Antigravity runtime with mechanism-enforced role permissions and JSON envelope validation."""
import json
import os

from ...policy.roles import build_antigravity_argv
from ..base import Capability, CapabilityManifest, CommandRuntime, InvocationRequest, InvocationResult


class AntigravityRuntime(CommandRuntime):
    provider = 'antigravity'
    executable = 'agy'
    manifest = CapabilityManifest(
        adapter='antigravity', kind='agent_runtime',
        capabilities={Capability.TEXT, Capability.PLANNING, Capability.CODE_EDIT, Capability.REPO_CONTEXT},
        permission_modes=['read_only', 'workspace_write'], auth_modes=['cli_managed'],
        billing_mode='unknown', usage_source='none', verified=False,
    )

    def _resolve_model(self, req: InvocationRequest):
        return req.model if req.model is not None else os.getenv(
            'ORCH_ANTIGRAVITY_MODEL', 'gemini-4-argon-medium',
        )

    def _invoke(self, req: InvocationRequest) -> InvocationResult:
        argv = build_antigravity_argv(
            role=req.role,
            permission=req.permission,
            prompt=req.prompt,
            model=req.model,
            supported_modes=self.manifest.permission_modes,
        )
        raw = self._run(argv, req)
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError('Antigravity returned invalid CLI JSON') from exc
        if result.get('status') != 'SUCCESS':
            raise RuntimeError(f'Antigravity failed: {result.get("status")}')
        denied_actions = result.get('denied_actions') or []
        if denied_actions:
            raise RuntimeError(
                'Antigravity denied requiredactions: '
                + json.dumps(denied_actions, ensure_ascii=False)
            )
        response = result.get('response')
        if not isinstance(response, str) or not response.strip():
            raise RuntimeError('Antigravity returned an empty or invalid response')
        return InvocationResult(text=response)
