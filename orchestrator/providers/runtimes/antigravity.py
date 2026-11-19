"""Antigravity runtime with mechanism-enforced role permissions and JSON envelope validation."""
import json
import os
import re

from ...policy.roles import build_antigravity_argv
from ..base import Capability, CapabilityManifest, CommandRuntime, InvocationRequest, InvocationResult


def _extract_structured_dict(text: str) -> dict:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.S)
        if not match:
            raise RuntimeError('Antigravity response was not valid JSON') from None
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise RuntimeError('Antigravity response was not valid JSON') from exc
    if not isinstance(parsed, dict):
        raise RuntimeError('Antigravity response must be a JSON object')
    return parsed


def validate_review_payload(payload: dict) -> dict:
    if type(payload.get('approved')) is not bool:
        raise RuntimeError('Antigravity reviewer must return boolean approved')
    findings = payload.get('findings')
    if not isinstance(findings, list) or any(not isinstance(item, str) for item in findings):
        raise RuntimeError('Antigravity reviewer must return string list findings')
    suggestions = payload.get('test_suggestions')
    if suggestions is not None and (
        not isinstance(suggestions, list) or any(not isinstance(item, str) for item in suggestions)
    ):
        raise RuntimeError('Antigravity reviewer test_suggestions must be a string list')
    normalized = {'approved': payload['approved'], 'findings': list(findings)}
    if suggestions is not None:
        normalized['test_suggestions'] = list(suggestions)
    for key, value in payload.items():
        if key not in normalized:
            normalized[key] = value
    return normalized


class AntigravityRuntime(CommandRuntime):
    provider = 'antigravity'
    executable = 'agy'
    manifest = CapabilityManifest(
        adapter='antigravity', kind='agent_runtime',
        capabilities={
            Capability.TEXT, Capability.PLANNING, Capability.CODE_EDIT,
            Capability.REVIEW, Capability.STRUCTURED_OUTPUT, Capability.REPO_CONTEXT,
        },
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
        structured = None
        if req.role == 'reviewer':
            structured = validate_review_payload(_extract_structured_dict(response))
        return InvocationResult(text=response, structured=structured)
