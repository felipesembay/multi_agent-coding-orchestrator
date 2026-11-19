"""Measured runtime calls and durable, content-free per-run metadata."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from orchestrator import core
from orchestrator.providers import base
from orchestrator.providers.base import InvocationRequest, UsageReport
from orchestrator.providers.runtimes.antigravity import AntigravityRuntime
from orchestrator.providers.runtimes.claude_code import ClaudeCodeRuntime
from orchestrator.providers.runtimes.codex_cli import CodexCliRuntime


@pytest.mark.parametrize('runtime,role,permission,output', [
    (ClaudeCodeRuntime, 'implementer', 'workspace_write', 'answer'),
    (CodexCliRuntime, 'reviewer', 'read_only', 'answer'),
    (AntigravityRuntime, 'planner', 'read_only', '{"status":"SUCCESS","response":"answer","usage":{"input_tokens":42},"session_id":"unverified"}'),
])
def test_results_are_measured_but_usage_is_unavailable(monkeypatch, runtime, role, permission, output):
    monkeypatch.setattr(base.time, 'monotonic_ns', Mock(side_effect=[1000000000, 1123000000]))
    observed = []
    result = runtime(Mock(return_value=output), observer=observed.append).invoke(
        InvocationRequest(prompt='task', cwd='/tmp', permission=permission, role=role))
    assert result.text == 'answer'
    assert result.duration_ms == 123
    assert result.structured is None
    assert result.model_reported is None
    assert result.session_id is None
    assert result.error_code is None
    assert result.usage == UsageReport()
    assert result.usage.source == 'unavailable'
    assert all(value is None for key, value in result.usage.model_dump().items() if key not in ('source', 'raw'))
    assert len(observed) == 1
    assert observed[0].duration_ms == 123
    assert observed[0].error_code is None
    assert observed[0].billing_mode == 'unknown'


@pytest.mark.parametrize('message,code', [
    ('claude exited 1: rate limit exceeded', 'rate_limited'),
    ('claude exited 1: usage limit reached', 'quota_exhausted'),
    ('authentication failed', 'auth_failed'),
    ('claude timed out after 4s', 'timeout'),
    ('Antigravity returned invalid CLI JSON', 'invalid_output'),
    ('Antigravity denied requiredactions: []', 'permission_denied'),
    ('Executable missing: claude', 'unavailable'),
    ('unrecognized error', 'unknown'),
])
def test_failure_metadata_preserves_original_exception(monkeypatch, message, code):
    monkeypatch.setattr(base.time, 'monotonic_ns', Mock(side_effect=[0, 25000000]))
    observed = []
    original = RuntimeError(message)
    runtime = ClaudeCodeRuntime(Mock(side_effect=original), observer=observed.append)
    with pytest.raises(RuntimeError) as caught:
        runtime.invoke(InvocationRequest(prompt='task', cwd='/tmp', permission='workspace_write'))
    assert caught.value is original
    assert len(observed) == 1
    assert observed[0].error_code == code
    assert observed[0].duration_ms == 25
    assert observed[0].usage == UsageReport()
    assert message not in observed[0].model_dump_json()


def test_unavailable_usage_cannot_claim_zero_or_cost():
    with pytest.raises(ValidationError):
        UsageReport(source='unavailable', input_tokens=0)
    with pytest.raises(ValidationError):
        UsageReport(source='estimated', reported_cost_usd=-1)
    one = UsageReport()
    one.raw['fixture'] = 'value'
    assert UsageReport().raw == {}


@pytest.fixture
def run_process(monkeypatch, tmp_path):
    monkeypatch.setenv('ORCH_DB', str(tmp_path / 'events.db'))
    for key in ('ORCH_PLANNER', 'ORCH_IMPLEMENTER', 'ORCH_PLANNER_MODEL', 'ORCH_IMPLEMENTER_MODEL', 'ORCH_ANTIGRAVITY_MODEL'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(core.shutil, 'which', lambda name, **kwargs: '/mock/' + name)
    runner = Mock(return_value=SimpleNamespace(returncode=0, stdout='answer', stderr=''))
    monkeypatch.setattr(core.subprocess, 'run', runner)
    return runner, {'run_id': 'metadata-run', 'worktree': str(tmp_path)}


def calls(state):
    return [payload for stage, payload in core._load_events(state['run_id']) if stage == 'agent_call']


@pytest.mark.parametrize('role', ['planner', 'implementer'])
def test_calls_are_linked_to_run_and_role(run_process, role):
    _, state = run_process
    assert core.coding_agent('task', state['worktree'], role, state=state) == 'answer'
    recorded = calls(state)
    assert len(recorded) == 1
    assert recorded[0]['provider'] == 'claude_code'
    assert recorded[0]['role'] == role
    assert recorded[0]['model'] is None
    assert recorded[0]['usage']['source'] == 'unavailable'
    assert recorded[0]['error_code'] is None


def test_quota_fallback_emits_one_call_per_attempt_without_secrets(run_process, monkeypatch):
    runner, state = run_process
    monkeypatch.setenv('SENTINEL_API_KEY', 'secret-environment')
    monkeypatch.setenv('ORCH_PLANNER_MODEL', 'requested-model')
    runner.side_effect = [
        SimpleNamespace(returncode=1, stdout='', stderr='usage limit reached secret-stderr'),
        SimpleNamespace(returncode=0, stdout='{"status":"SUCCESS","response":"secret-output"}', stderr=''),
    ]
    assert core.coding_agent('secret-prompt', state['worktree'], 'planner', state=state) == 'secret-output'
    recorded = calls(state)
    assert [call['provider'] for call in recorded] == ['claude_code', 'antigravity']
    assert [call['error_code'] for call in recorded] == ['quota_exhausted', None]
    assert [call['model'] for call in recorded] == [None, 'requested-model']
    assert len({call['call_id'] for call in recorded}) == 2
    assert [stage for stage, _ in core._load_events(state['run_id'])] == ['agent_call', 'agent_fallback', 'agent_call']
    serialized = json.dumps(recorded)
    for sentinel in ('secret-environment', 'secret-stderr', 'secret-output', 'secret-prompt'):
        assert sentinel not in serialized
    assert all('raw' not in call['usage'] for call in recorded)


def test_workflow_roles_and_review_are_instrumented(run_process, monkeypatch):
    runner, state = run_process
    state.update(scope='make task', managed=True)
    responses = [
        '{"tasks":[{"id":"T1","title":"task","instructions":"do it","acceptance":[]}]}',
        'implemented', '{"approved":true,"findings":[]}',
    ]
    def run(argv, **kwargs):
        if argv[0] in ('claude', 'codex'):
            return SimpleNamespace(returncode=0, stdout=responses.pop(0), stderr='')
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    runner.side_effect = run
    monkeypatch.setenv('ORCH_TEST_COMMAND', 'pytest')
    state.update(core.plan(state))
    state.update(core.implement(state))
    state.update(core.review(state))
    assert state['review']['approved'] is True
    assert [call['role'] for call in calls(state)] == ['planner', 'implementer', 'reviewer']
    assert [call['provider'] for call in calls(state)] == ['claude_code', 'claude_code', 'codex_cli']
    assert len(calls(state)) == 3  # Git and test commands are not agent calls.


def test_context_is_reset_after_failure(run_process):
    runner, state = run_process
    runner.return_value = SimpleNamespace(returncode=1, stdout='', stderr='authentication failed')
    with pytest.raises(RuntimeError):
        core.coding_agent('task', state['worktree'], 'planner', state=state)
    runner.return_value = SimpleNamespace(returncode=0, stdout='standalone', stderr='')
    assert core.claude('task', state['worktree']) == 'standalone'
    assert len(calls(state)) == 1  # No previous run is inherited by a standalone call.


def test_telemetry_failure_does_not_replace_agent_failure(caplog):
    original = RuntimeError('authentication failed: secret-message')
    runtime = ClaudeCodeRuntime(Mock(side_effect=original), observer=Mock(side_effect=OSError('secret-db')))
    with pytest.raises(RuntimeError) as caught:
        runtime.invoke(InvocationRequest(prompt='task', cwd='/tmp', permission='workspace_write'))
    assert caught.value is original
    assert 'Could not record failed agent call metadata' in caplog.text
    assert 'secret-message' not in caplog.text
    assert 'secret-db' not in caplog.text


def test_invalid_antigravity_output_is_recorded_as_failure(run_process, monkeypatch):
    runner, state = run_process
    monkeypatch.setenv('ORCH_PLANNER', 'antigravity')
    monkeypatch.setenv('ORCH_ANTIGRAVITY_MODEL', 'direct-model')
    runner.return_value.stdout = 'not json secret-output'
    with pytest.raises(RuntimeError, match='invalid CLI JSON'):
        core.coding_agent('task', state['worktree'], 'planner', state=state)
    recorded = calls(state)
    assert len(recorded) == 1
    assert recorded[0]['error_code'] == 'invalid_output'
    # coding_agent's legacy per-role default takes precedence over the direct facade env.
    assert recorded[0]['model'] == 'gemini-4-argon-medium'
    assert 'secret-output' not in json.dumps(recorded)


def test_direct_antigravity_observer_sees_effective_default_model(monkeypatch):
    monkeypatch.setenv('ORCH_ANTIGRAVITY_MODEL', 'effective-env-model')
    observed = []
    runtime = AntigravityRuntime(Mock(return_value='{"status":"SUCCESS","response":"ok"}'), observer=observed.append)
    runtime.invoke(InvocationRequest(prompt='task', cwd='/tmp', permission='read_only'))
    assert observed[0].model == 'effective-env-model'
    assert observed[0].model_reported is None


def test_invalid_plugin_result_is_recorded_without_return_value_content():
    observed = []
    request = InvocationRequest(prompt='task', cwd='/tmp', permission='read_only')
    invalid_return = 'secret-invalid-return'
    with pytest.raises(RuntimeError, match='invalid InvocationResult') as caught:
        base.invoke_measured('broken_plugin', request, lambda: invalid_return, observed.append)
    assert 'secret-invalid-return' not in str(caught.value)
    import traceback
    assert 'secret-invalid-return' not in ''.join(traceback.format_exception(
        type(caught.value), caught.value, caught.value.__traceback__))
    assert len(observed) == 1
    assert observed[0].error_code == 'invalid_output'
    assert 'secret-invalid-return' not in observed[0].model_dump_json()
