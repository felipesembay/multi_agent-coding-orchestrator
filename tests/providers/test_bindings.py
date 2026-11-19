"""Bindings resolve once from legacy inputs and validate before agent execution."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from orchestrator import core
from orchestrator.providers import bindings, registry
from orchestrator.providers.base import CapabilityManifest, InvocationResult, ProbeResult


@pytest.fixture(autouse=True)
def clean_agent_environment(monkeypatch):
    for key in ('ORCH_PLANNER', 'ORCH_IMPLEMENTER', 'ORCH_PLANNER_MODEL',
                'ORCH_IMPLEMENTER_MODEL', 'ORCH_ANTIGRAVITY_MODEL', 'AGENT_TIMEOUT'):
        monkeypatch.delenv(key, raising=False)


def test_legacy_defaults_and_explicit_models_are_resolved():
    config = bindings.legacy_bindings({})
    assert config.planner.adapter == config.implementer.adapter == 'claude_code'
    assert config.reviewer.adapter == 'codex_cli'
    assert config.planner.permission == 'read_only'
    assert config.implementer.permission == 'workspace_write'
    assert config.reviewer.permission == 'read_only'
    assert config.agent_timeout == 900
    assert config.planner_fallback.model == 'gemini-4-argon-medium'
    config = bindings.legacy_bindings({'ORCH_PLANNER': 'ANTIGRAVITY', 'ORCH_PLANNER_MODEL': '',
                                      'ORCH_IMPLEMENTER': 'antigravity', 'ORCH_IMPLEMENTER_MODEL': 'custom'})
    assert config.planner.adapter == 'antigravity' and config.planner.model == ''
    assert config.implementer.model == 'custom'
    assert config.planner_fallback is None


def test_old_flat_snapshot_ignores_current_environment(monkeypatch):
    snapshot = dict(planner='claude', implementer='antigravity', reviewer='codex',
                    planner_model=None, implementer_model='saved-model',
                    planner_fallback_model='saved-fallback', agent_timeout=77)
    monkeypatch.setenv('ORCH_PLANNER', 'unsupported')
    monkeypatch.setenv('ORCH_IMPLEMENTER_MODEL', 'new-model')
    result = bindings.bindings_from_snapshot(snapshot)
    assert result.implementer.model == 'saved-model'
    assert result.planner_fallback.model == 'saved-fallback'
    assert result.agent_timeout == 77
    assert result.reviewer.adapter == 'codex_cli'


@pytest.mark.parametrize('role,change', [
    ('implementer', {'adapter': 'codex_cli'}),
    ('reviewer', {'adapter': 'claude_code'}),
    ('reviewer', {'permission': 'workspace_write'}),
    ('planner', {'model': 'not-supported-by-legacy-cli'}),
])
def test_unsupported_role_permission_or_model_is_rejected(role, change):
    value = bindings.legacy_bindings({}).model_dump()
    value[role].update(change)
    with pytest.raises(ValueError):
        bindings.validate_bindings(bindings.AgentBindings.model_validate(value), registry.ProviderRegistry())


def test_snapshot_is_immutable_and_validates_nested_fields():
    from pydantic import ValidationError
    config = bindings.legacy_bindings({})
    with pytest.raises(ValidationError):
        config.planner.adapter = 'antigravity'
    value = config.model_dump()
    value['reviewer']['permission'] = 'unrestricted'
    with pytest.raises(ValidationError):
        bindings.AgentBindings.model_validate(value)


def test_frozen_roles_models_and_fallback_survive_env_changes(monkeypatch, tmp_path):
    config = bindings.legacy_bindings({'ORCH_PLANNER_MODEL': 'saved-fallback', 'AGENT_TIMEOUT': '73'})
    state = {'run_id': 'binding-call', 'worktree': str(tmp_path), 'bindings': config.model_dump()}
    monkeypatch.setenv('ORCH_DB', str(tmp_path / 'events.db'))
    monkeypatch.setenv('ORCH_PLANNER', 'antigravity')
    monkeypatch.setenv('ORCH_PLANNER_MODEL', 'mutated-model')
    monkeypatch.setenv('AGENT_TIMEOUT', '1')
    primary = Mock(side_effect=RuntimeError('usage limit reached'))
    fallback = Mock(return_value='plan')
    monkeypatch.setattr(core, 'claude', primary)
    monkeypatch.setattr(core, 'antigravity', fallback)
    assert core.coding_agent('task', str(tmp_path), 'planner', state=state) == 'plan'
    primary.assert_called_once_with('task', str(tmp_path), 73)
    fallback.assert_called_once_with('task', str(tmp_path), timeout=73, mode='plan', model='saved-fallback')


def test_reviewer_is_configurable_internally_with_registered_runtime(monkeypatch, tmp_path):
    seen = []
    class FakeReviewer:
        manifest = CapabilityManifest(adapter='fake_review', kind='agent_runtime',
            capabilities={'text', 'review'}, permission_modes=['read_only'], auth_modes=['none'],
            billing_mode='local', usage_source='none', verified=False)
        def probe(self):
            return ProbeResult()
        def invoke(self, request):
            seen.append(request)
            return InvocationResult(text='{"approved":true,"findings":[]}')
    entry = SimpleNamespace(name='fake_review', load=lambda: FakeReviewer)
    monkeypatch.setattr(registry.metadata, 'entry_points', lambda: {'orchestrator.providers': [entry]})
    catalog = registry.ProviderRegistry(enabled_entry_points=['fake_review'])
    config = bindings.legacy_bindings({}).model_dump()
    config['reviewer'] = dict(adapter='fake_review', model='review-model', permission='read_only')
    monkeypatch.setenv('ORCH_DB', str(tmp_path / 'events.db'))
    monkeypatch.setenv('ORCH_TEST_COMMAND', 'pytest -q')
    monkeypatch.setattr(core, 'run_command', Mock(return_value=''))
    state = dict(run_id='custom-review', worktree=str(tmp_path), task_index=0,
                 plan={'tasks': [{'id': 'T1'}]}, bindings=config)
    with core._using_provider_registry(catalog):
        result = core.review(state)
    assert result['review']['approved'] is True
    assert len(seen) == 1
    assert seen[0].role == 'reviewer' and seen[0].permission == 'read_only'
    assert seen[0].model == 'review-model'
    calls = [p for stage, p in core._load_events(state['run_id']) if stage == 'agent_call']
    assert len(calls) == 1 and calls[0]['provider'] == 'fake_review'


def test_new_unverified_executor_is_rejected(monkeypatch):
    class Unverified:
        manifest = CapabilityManifest(adapter='unverified', kind='agent_runtime',
            capabilities={'text', 'code_edit'}, permission_modes=['workspace_write'], auth_modes=['none'],
            billing_mode='unknown', usage_source='none', verified=False)
        def probe(self):
            return ProbeResult()
        def invoke(self, request):
            raise AssertionError('Must not invoke unverified executor')
    entry = SimpleNamespace(name='unverified', load=lambda: Unverified)
    monkeypatch.setattr(registry.metadata, 'entry_points', lambda: {'orchestrator.providers': [entry]})
    catalog = registry.ProviderRegistry(enabled_entry_points=['unverified'])
    value = bindings.legacy_bindings({}).model_dump()
    value['implementer']['adapter'] = 'unverified'
    with pytest.raises(ValueError, match='verified'):
        bindings.validate_bindings(bindings.AgentBindings.model_validate(value), catalog)


def test_execute_scope_saves_resolved_bindings_before_graph(monkeypatch, tmp_path):
    from contextlib import nullcontext
    monkeypatch.setenv('ORCH_DB', str(tmp_path / 'events.db'))
    monkeypatch.setattr(core, 'repository_lock', lambda repo: nullcontext())
    monkeypatch.setattr(core, 'prepare', lambda repo, run_id: tmp_path / run_id)
    def invoke(state, entry_point):
        assert state['bindings']['reviewer']['adapter'] == 'codex_cli'
        monkeypatch.setenv('ORCH_PLANNER', 'unsupported')
        assert bindings.AgentBindings.model_validate(state['bindings']).planner.adapter == 'claude_code'
        return state
    monkeypatch.setattr(core, '_invoke', invoke)
    state = core.execute_scope(str(tmp_path), 'scope')
    start = core._load_events(state['run_id'])[0][1]
    assert start['bindings'] == state['bindings']


def test_antigravity_default_is_resolved_without_direct_facade_environment(monkeypatch):
    config = bindings.legacy_bindings({}).model_dump()
    config['planner'] = dict(adapter='antigravity', permission='read_only', model=None)
    config['planner_fallback'] = None
    monkeypatch.setenv('ORCH_ANTIGRAVITY_MODEL', 'must-not-leak-into-snapshot')
    parsed = bindings.AgentBindings.model_validate(config)
    assert parsed.planner.model == 'gemini-4-argon-medium'
    bindings.validate_bindings(parsed, registry.ProviderRegistry())


def test_resume_restores_saved_bindings_instead_of_environment(monkeypatch, tmp_path):
    run_id = 'run-' + '1' * 12
    repo, base = tmp_path / 'repo', tmp_path / 'trees'
    tree = base / run_id
    repo.mkdir()
    tree.mkdir(parents=True)
    monkeypatch.setenv('ORCH_DB', str(tmp_path / 'events.db'))
    monkeypatch.setenv('ORCH_WORKTREES', str(base))
    saved = bindings.legacy_bindings({'ORCH_IMPLEMENTER': 'antigravity', 'ORCH_IMPLEMENTER_MODEL': 'saved-model'}).model_dump()
    core.event({'run_id': run_id}, 'started', {'repo': str(repo), 'worktree': str(tree), 'bindings': saved})
    core.event({'run_id': run_id}, 'plan', {'tasks': [{'id': 'T1'}]})
    monkeypatch.setenv('ORCH_PLANNER', 'unsupported')
    monkeypatch.setenv('ORCH_IMPLEMENTER_MODEL', 'drift')
    monkeypatch.setattr(core, 'run_command', Mock(return_value=str(tree)))
    result = core.resume(run_id, dry_run=True)
    assert result['bindings'] == saved
    assert result['entry_point'] == 'implement'


@pytest.mark.parametrize('planner_model', [None, ''])
def test_old_managed_planner_null_or_empty_uses_saved_fallback(planner_model):
    snapshot = dict(planner='antigravity', implementer='claude', reviewer='codex',
                    planner_model=planner_model, implementer_model=None,
                    planner_fallback_model='saved-fallback', agent_timeout=900)
    assert bindings.bindings_from_snapshot(snapshot).planner.model == 'saved-fallback'
    snapshot['planner'] = 'claude'
    assert bindings.bindings_from_snapshot(snapshot).planner_fallback.model == 'saved-fallback'


@pytest.mark.parametrize('implementer_model', [None, ''])
def test_old_managed_implementer_null_or_empty_uses_cli_default(implementer_model):
    snapshot = dict(planner='claude', implementer='antigravity', reviewer='codex',
                    planner_model=None, implementer_model=implementer_model,
                    planner_fallback_model='saved-fallback', agent_timeout=900)
    assert bindings.bindings_from_snapshot(snapshot).implementer.model == 'gemini-4-argon-medium'


def test_direct_environment_preserves_empty_models_for_both_roles():
    config = bindings.legacy_bindings({'ORCH_PLANNER': 'antigravity', 'ORCH_PLANNER_MODEL': '',
                                     'ORCH_IMPLEMENTER': 'antigravity', 'ORCH_IMPLEMENTER_MODEL': ''})
    assert config.planner.model == config.implementer.model == ''


def test_graph_freezes_bindings_and_propagates_registry_context(monkeypatch, tmp_path):
    from contextlib import nullcontext
    seen, commands = [], []
    class FakeReviewer:
        manifest = CapabilityManifest(adapter='fake_review', kind='agent_runtime',
            capabilities={'text', 'review'}, permission_modes=['read_only'], auth_modes=['none'],
            billing_mode='local', usage_source='none', verified=False)
        def probe(self):
            return ProbeResult()
        def invoke(self, request):
            seen.append(request)
            return InvocationResult(text='{"approved":true,"findings":[]}')
    entry = SimpleNamespace(name='fake_review', load=lambda: FakeReviewer)
    monkeypatch.setattr(registry.metadata, 'entry_points', lambda: {'orchestrator.providers': [entry]})
    catalog = registry.ProviderRegistry(enabled_entry_points=['fake_review'])
    config = bindings.legacy_bindings({}).model_dump()
    config['reviewer'] = dict(adapter='fake_review', permission='read_only', model='saved-model')
    monkeypatch.setenv('ORCH_DB', str(tmp_path / 'events.db'))
    monkeypatch.setenv('ORCH_TEST_COMMAND', 'pytest -q')
    monkeypatch.setattr(core, 'repository_lock', lambda repo: nullcontext())
    monkeypatch.setattr(core, 'prepare', lambda repo, run_id: tmp_path / run_id)
    def run(argv, cwd, timeout=600, env=None):
        if argv[0] == 'claude':
            commands.append((argv, timeout))
            if len(commands) == 1:
                monkeypatch.setenv('ORCH_IMPLEMENTER', 'unsupported')
                monkeypatch.setenv('AGENT_TIMEOUT', '1')
                return '{"tasks":[{"id":"T1","title":"task","instructions":"do it","acceptance":[]}]}'
            return 'implemented'
        return ''
    monkeypatch.setattr(core, 'run_command', run)
    result = core.execute_scope(str(tmp_path), 'scope', bindings=config, provider_registry=catalog)
    assert result['status'] == 'ready_for_human_review'
    assert [timeout for _, timeout in commands] == [900, 900]
    assert len(seen) == 1 and seen[0].model == 'saved-model'
    calls = [payload for stage, payload in core._load_events(result['run_id']) if stage == 'agent_call']
    assert [call['provider'] for call in calls] == ['claude_code', 'claude_code', 'fake_review']
