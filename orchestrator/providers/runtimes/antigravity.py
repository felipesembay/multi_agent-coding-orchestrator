"""Antigravity legacy argv and JSON envelope validation."""
import json
import os

from ..base import CommandRuntime, InvocationRequest, InvocationResult


class AntigravityRuntime(CommandRuntime):
    def invoke(self, req: InvocationRequest) -> InvocationResult:
        mode = 'plan' if req.permission == 'read_only' else 'accept-edits'
        model = req.model
        if model is None:
            model = os.getenv('ORCH_ANTIGRAVITY_MODEL', 'gemini-4-argon-medium')
        raw = self._run([
            'agy', '--print', req.prompt, '--model', model,
            '--mode', mode, '--output-format', 'json',
        ], req)
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
