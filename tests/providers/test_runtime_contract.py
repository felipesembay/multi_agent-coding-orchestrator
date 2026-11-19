"""New adapter boundary: execution stays injectable, policy is explicit."""
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from orchestrator.providers.base import AgentRuntime, InvocationRequest
from orchestrator.providers.runtimes.antigravity import AntigravityRuntime
from orchestrator.providers.runtimes.claude_code import ClaudeCodeRuntime
from orchestrator.providers.runtimes.codex_cli import CodexCliRuntime


@pytest.mark.parametrize('runtime,role,permission,output', [
    (ClaudeCodeRuntime, 'planner', 'read_only', 'text'),
    (ClaudeCodeRuntime, 'implementer', 'workspace_write', 'text'),
    (CodexCliRuntime, 'reviewer', 'read_only', 'text'),
    (CodexCliRuntime, 'implementer', 'workspace_write', 'text'),
    (AntigravityRuntime, 'planner', 'read_only', '{"status":"SUCCESS","response":"text"}'),
    (AntigravityRuntime, 'implementer', 'workspace_write', '{"status":"SUCCESS","response":"text"}'),
])
def test_runtime_injects_runner_and_passes_explicit_environment(runtime, role, permission, output):
    runner = Mock(return_value=output)
    adapter: AgentRuntime = runtime(runner)
    request = InvocationRequest(prompt='task', cwd='/tmp/tree', role=role,
                                permission=permission, timeout_s=17, env={'LANG': 'C'})
    assert adapter.invoke(request).text == 'text'
    assert runner.call_count == 1
    assert runner.call_args.args[1:] == ('/tmp/tree', 17)
    assert runner.call_args.kwargs['env']['LANG'] == 'C'
    assert set(runner.call_args.kwargs['env']) <= {'LANG', 'GIT_CONFIG_GLOBAL', 'GIT_CONFIG_NOSYSTEM', 'ORCH_DISPATCH_TOKEN'}


@pytest.mark.parametrize('runtime,role,permission', [
    (ClaudeCodeRuntime, 'planner', 'workspace_write'),
    (CodexCliRuntime, 'reviewer', 'workspace_write'),
    (CodexCliRuntime, 'implementer', 'read_only'),
    (AntigravityRuntime, 'reviewer', 'workspace_write'),
])
def test_runtime_rejects_disallowed_role_permission(runtime, role, permission):
    runner = Mock()
    with pytest.raises(ValueError, match='not permitted'):
        runtime(runner).invoke(InvocationRequest(role=role, prompt='task', cwd='/tmp', permission=permission))
    runner.assert_not_called()


def test_unknown_permission_rejected_before_execution():
    with pytest.raises(ValidationError):
        InvocationRequest(prompt='task', cwd='/tmp', permission='unrestricted')
