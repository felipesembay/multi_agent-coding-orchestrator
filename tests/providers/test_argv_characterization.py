"""Frozen CLI contract, first run against core before extracting adapters.

Never invoke agents: replace executable discovery and subprocess.run at the
process boundary so argv, cwd, timeout, environment and lock forwarding are seen.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from orchestrator import core


PROMPT = 'Task with spaces, "quotes", $HOME and\na second line'
CWD = '/tmp/characterization worktree'
AGY_TEXT = '{"tasks": []}'
AGY_OUTPUT = json.dumps({'status': 'SUCCESS', 'response': AGY_TEXT})


@pytest.fixture
def process(monkeypatch):
    for name in ('ORCH_PLANNER', 'ORCH_IMPLEMENTER', 'ORCH_PLANNER_MODEL',
                 'ORCH_IMPLEMENTER_MODEL', 'ORCH_ANTIGRAVITY_MODEL', 'AGENT_TIMEOUT'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(core.shutil, 'which', lambda executable, **kwargs: '/mock/' + executable)
    runner = Mock(return_value=SimpleNamespace(returncode=0, stdout='output', stderr=''))
    monkeypatch.setattr(core.subprocess, 'run', runner)
    token = core.lock_fd.set(None)
    yield runner
    core.lock_fd.reset(token)


def assert_process(call, argv, timeout):
    assert call.args == (argv,)
    kwargs = dict(call.kwargs)
    env = kwargs.pop('env')
    assert isinstance(env, dict)  # SEC-002 intentionally replaces env=None with a filtered map.
    assert 'ORCH_DB' not in env and 'OPENAI_API_KEY' not in env
    assert kwargs == dict(cwd=CWD, text=True, capture_output=True,
                          timeout=timeout, check=False, pass_fds=())


@pytest.mark.parametrize('role,expected_flags', [
    ('planner', ['--permission-mode', 'plan']),
    ('implementer', ['--permission-mode', 'acceptEdits', '--disallowedTools', 'Bash']),
])
@pytest.mark.parametrize('timeout', [None, '123'])
def test_claude_roles(process, monkeypatch, role, expected_flags, timeout):
    if timeout:
        monkeypatch.setenv('AGENT_TIMEOUT', timeout)
    assert core.coding_agent(PROMPT, CWD, role) == 'output'
    assert process.call_count == 1
    assert_process(process.call_args,
                   ['claude', '-p', *expected_flags, PROMPT],
                   int(timeout or '900'))


@pytest.mark.parametrize('role,mode', [('planner', 'plan'), ('implementer', 'accept-edits')])
@pytest.mark.parametrize('model', [None, 'custom-model'])
def test_antigravity_roles(process, monkeypatch, role, mode, model):
    monkeypatch.setenv('ORCH_' + role.upper(), 'antigravity')
    monkeypatch.setenv('AGENT_TIMEOUT', '321')
    if model is not None:
        monkeypatch.setenv('ORCH_' + role.upper() + '_MODEL', model)
    process.return_value.stdout = AGY_OUTPUT
    assert core.coding_agent(PROMPT, CWD, role) == AGY_TEXT
    assert process.call_count == 1
    assert_process(process.call_args,
                   ['agy', '--print', PROMPT, '--model', model or 'gemini-4-argon-medium',
                    '--mode', mode, '--output-format', 'json'], 321)


def test_codex_reviewer(process):
    assert core.codex(PROMPT, CWD, timeout=456) == 'output'
    assert_process(process.call_args, ['codex', 'exec', '--sandbox', 'read-only', PROMPT], 456)


@pytest.mark.parametrize('provider,timeout', [('claude', 600), ('codex', 600), ('antigravity', 900)])
def test_direct_facade_defaults(process, provider, timeout):
    if provider == 'antigravity':
        process.return_value.stdout = AGY_OUTPUT
    getattr(core, provider)(PROMPT, CWD)
    assert process.call_args.kwargs['timeout'] == timeout


@pytest.mark.parametrize('model', [None, 'env-model', ''])
def test_antigravity_direct_model_default(process, monkeypatch, model):
    if model is not None:
        monkeypatch.setenv('ORCH_ANTIGRAVITY_MODEL', model)
    process.return_value.stdout = AGY_OUTPUT
    assert core.antigravity(PROMPT, CWD) == AGY_TEXT
    assert_process(process.call_args,
                   ['agy', '--print', PROMPT, '--model', model if model is not None else 'gemini-4-argon-medium',
                    '--mode', 'plan', '--output-format', 'json'], 900)


def test_antigravity_explicit_model_overrides_environment(process, monkeypatch):
    monkeypatch.setenv('ORCH_ANTIGRAVITY_MODEL', 'env-model')
    process.return_value.stdout = AGY_OUTPUT
    core.antigravity(PROMPT, CWD, model='explicit-model', mode='accept-edits')
    assert_process(process.call_args,
                   ['agy', '--print', PROMPT, '--model', 'explicit-model',
                    '--mode', 'accept-edits', '--output-format', 'json'], 900)


def test_planner_quota_fallback(process, monkeypatch):
    monkeypatch.setenv('ORCH_PLANNER_MODEL', 'fallback-model')
    monkeypatch.setenv('AGENT_TIMEOUT', '234')
    process.side_effect = [SimpleNamespace(returncode=1, stdout='', stderr='usage limit reached'),
                           SimpleNamespace(returncode=0, stdout=AGY_OUTPUT, stderr='')]
    assert core.coding_agent(PROMPT, CWD, 'planner') == AGY_TEXT
    assert len(process.call_args_list) == 2
    assert_process(process.call_args_list[0],
                   ['claude', '-p', '--permission-mode', 'plan', PROMPT], 234)
    assert_process(process.call_args_list[1],
                   ['agy', '--print', PROMPT, '--model', 'fallback-model',
                    '--mode', 'plan', '--output-format', 'json'], 234)


@pytest.mark.parametrize('raw,message', [
    ('not json', 'Antigravity returned invalid CLI JSON'),
    ('{"status":"FAILED"}', 'Antigravity failed: FAILED'),
    ('{"status":"SUCCESS","denied_actions":["write"]}', 'Antigravity denied requiredactions:'),
    ('{"status":"SUCCESS","response":" "}', 'Antigravity returned an empty or invalid response'),
])
def test_antigravity_output_errors_unchanged(process, raw, message):
    process.return_value.stdout = raw
    with pytest.raises(RuntimeError, match=message):
        core.antigravity(PROMPT, CWD)


def test_invalid_antigravity_mode_never_starts_process(process):
    with pytest.raises(ValueError, match='Invalid Antigravity mode: invalid'):
        core.antigravity(PROMPT, CWD, mode='invalid')
    process.assert_not_called()
