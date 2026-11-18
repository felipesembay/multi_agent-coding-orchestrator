from types import SimpleNamespace
from contextlib import nullcontext
import json

import pytest
from pydantic import ValidationError

from orchestrator.providers.base import CapabilityManifest, InvocationRequest, InvocationResult
from orchestrator.providers.bindings import AgentBindings, legacy_bindings
from orchestrator.providers.registry import ProviderRegistry
from orchestrator.workflows.presets import (
    PresetUnavailableError, clone_preset, get_default_preset, get_preset,
    list_presets, validate_preset,
)
from orchestrator.workflows.validation import validate_workflow
from orchestrator.workflows.compiler import compile_workflow


@pytest.fixture
def registry():
    manifests = {}
    for adapter in ('claude_code', 'codex_cli', 'antigravity', 'openrouter', 'custom'):
        manifests[adapter] = CapabilityManifest(
            adapter=adapter, kind='model_provider' if adapter == 'openrouter' else 'agent_runtime',
            capabilities=['text', 'planning', 'structured_output', 'review'] + ([] if adapter == 'openrouter' else ['code_edit']),
            permission_modes=['read_only'] if adapter == 'openrouter' else ['read_only', 'workspace_write'],
            auth_modes=['none'], billing_mode='unknown', usage_source='none', verified=True,
        )
    class FakeRegistry:
        def get(self, adapter):
            return SimpleNamespace(manifest=manifests[adapter])
    return FakeRegistry()


@pytest.mark.parametrize('preset_id,adapters', [
    ('default-v2', ['claude_code', 'codex_cli', 'antigravity']),
    ('openrouter-plan', ['openrouter', 'codex_cli', 'claude_code']),
    ('claude-heavy', ['claude_code', 'claude_code', 'codex_cli']),
])
def test_templates_validate_with_honest_fakes(registry, preset_id, adapters):
    preset = get_preset(preset_id)
    workflow = preset.workflow
    assert [workflow.provider_configs[workflow.bindings[step].provider_config_id]
            for step in ('plan', 'impl', 'review')] == adapters
    assert [s.type for s in workflow.definition.steps] == ['plan', 'implement', 'test', 'review']
    assert workflow.bindings['plan'].permission == workflow.bindings['review'].permission == 'read_only'
    assert workflow.bindings['impl'].permission == 'workspace_write'
    validate_workflow(workflow.definition, workflow.bindings, provider_configs=workflow.provider_configs, registry=registry)


def test_default_and_legacy_catalog_are_explicit():
    assert [preset.id for preset in list_presets()] == ['legacy-v1', 'default-v2', 'openrouter-plan', 'claude-heavy']
    assert get_default_preset('cli').id == 'legacy-v1'
    assert get_default_preset('ui').id == 'default-v2'
    assert get_preset('legacy-v1').execution_mode == 'legacy'
    assert get_preset('legacy-v1').workflow is None  # no claim that split test/review is identical


def test_openrouter_preset_is_disabled_even_with_fakes(registry):
    assert get_preset('openrouter-plan').blocked_by == ('V2-PROV-001',)
    with pytest.raises(PresetUnavailableError, match='V2-PROV-001'):
        validate_preset('openrouter-plan', registry=registry)


@pytest.mark.parametrize('preset_id', ['default-v2', 'claude-heavy'])
def test_new_presets_validate_against_actual_manifests(preset_id):
    with pytest.raises(ValidationError):
        validate_preset(preset_id, registry=ProviderRegistry())


def test_system_catalog_cannot_be_changed_via_returned_values():
    preset = get_preset('default-v2')
    with pytest.raises(ValidationError):
        preset.read_only = False
    preset.workflow.definition.steps[1].max_attempts = 0
    preset.workflow.bindings['plan'].model = 'modified'
    preset.workflow.provider_configs['pc-claude'] = 'modified'
    clean = get_preset('default-v2')
    assert clean.workflow.definition.steps[1].max_attempts == 3
    assert clean.workflow.bindings['plan'].model is None
    assert clean.workflow.provider_configs['pc-claude'] == 'claude_code'


def test_clone_and_stage_choices_do_not_modify_system_preset(registry):
    choices = {'plan': {'provider_config_id': 'custom-config', 'model': 'chosen-model',
                        'parameters': {'temperature': 0.2}, 'permission': 'read_only'}}
    draft = clone_preset('default-v2', name='Meu workflow', choices=choices,
                         provider_configs={'custom-config': 'custom'})
    assert draft.definition.name == 'Meu workflow'
    assert draft.bindings['plan'].model == 'chosen-model'
    assert draft.bindings['plan'].parameters == {'temperature': 0.2}
    choices['plan']['model'] = 'changed-after-clone'
    assert draft.bindings['plan'].model == 'chosen-model'
    validate_workflow(draft.definition, draft.bindings, provider_configs=draft.provider_configs, registry=registry)
    assert get_preset('default-v2').workflow.bindings['plan'].model is None


def test_legacy_resolution_preserves_exact_existing_configuration():
    env = {'ORCH_PLANNER': 'antigravity', 'ORCH_IMPLEMENTER': 'antigravity',
           'ORCH_PLANNER_MODEL': '', 'ORCH_IMPLEMENTER_MODEL': 'saved', 'AGENT_TIMEOUT': '77'}
    actual = validate_preset('legacy-v1', registry=ProviderRegistry(), environ=env)
    assert actual == legacy_bindings(env)
    assert actual.planner.model == ''
    assert actual.agent_timeout == 77


def test_clone_legacy_is_strict_user_workflow(registry):
    env = {'ORCH_PLANNER': 'antigravity', 'ORCH_PLANNER_MODEL': 'old-model'}
    draft = clone_preset('legacy-v1', name='legacy-v1', environ=env)
    assert draft.bindings['plan'].model == 'old-model'
    assert draft.bindings['plan'].permission == 'read_only'
    assert 'execution_mode' not in draft.model_dump()
    validate_workflow(draft.definition, draft.bindings, provider_configs=draft.provider_configs, registry=registry)
    draft.bindings['plan'].permission = 'workspace_write'
    with pytest.raises(ValidationError):
        validate_workflow(draft.definition, draft.bindings, provider_configs=draft.provider_configs, registry=registry)


@pytest.mark.parametrize('replacement', [None, 'chosen-model'])
def test_clone_legacy_normalizes_empty_model_and_allows_override(replacement):
    choices = None if replacement is None else {'plan': {
        'provider_config_id': 'pc-legacy-plan', 'model': replacement, 'permission': 'read_only'}}
    env = {'ORCH_PLANNER': 'antigravity', 'ORCH_PLANNER_MODEL': ''}
    draft = clone_preset('legacy-v1', name='strict draft', environ=env, choices=choices)
    assert draft.bindings['plan'].model == replacement
    assert validate_preset('legacy-v1', registry=ProviderRegistry(), environ=env).planner.model == ''


def test_legacy_customization_requires_clone():
    with pytest.raises(ValueError, match='clone'):
        validate_preset('legacy-v1', registry=ProviderRegistry(), choices={'plan': {'provider_config_id': 'new'}})


def test_no_catalog_discovery_or_ambient_model_dependency(monkeypatch):
    monkeypatch.setenv('ORCH_PLANNER', 'invalid')
    monkeypatch.setenv('AGENT_TIMEOUT', 'invalid')
    assert get_preset('default-v2').workflow.bindings['plan'].model is None
    assert len(list_presets()) == 4


@pytest.mark.parametrize('preset_id', ['missing', None, 'DEFAULT-V2'])
def test_unknown_preset_is_rejected(preset_id):
    with pytest.raises(ValueError, match='preset'):
        get_preset(preset_id)


@pytest.mark.parametrize('choices', [[], 'bad', {'tests': {'provider_config_id': 'pc'}},
                                     {'missing': {'provider_config_id': 'pc'}},
                                     {'impl': {'provider_config_id': 'pc', 'extra': 1}}])
def test_invalid_stage_choices_are_rejected(choices):
    with pytest.raises((ValidationError, ValueError)):
        clone_preset('default-v2', name='draft', choices=choices)


@pytest.mark.parametrize('name', ['', '   '])
def test_clone_name_must_be_valid(name):
    with pytest.raises(ValidationError):
        clone_preset('default-v2', name=name)


def test_selection_does_not_inherit_write_permission(registry):
    # Whole binding replacement requires the caller to choose write permission.
    with pytest.raises(ValidationError):
        validate_preset('default-v2', registry=registry, choices={
            'impl': {'provider_config_id': 'custom-config'}},
            provider_configs={'custom-config': 'custom'})


def test_legacy_catalog_and_resolution_are_separate(monkeypatch):
    monkeypatch.setenv('AGENT_TIMEOUT', 'invalid')
    assert get_default_preset('cli').id == 'legacy-v1'
    with pytest.raises(ValueError):
        validate_preset('legacy-v1', registry=ProviderRegistry())


@pytest.mark.parametrize('preset_id', ['default-v2', 'claude-heavy'])
def test_preset_executes_with_fakes_and_custom_provider_and_model(registry, preset_id):
    requests = []
    get = registry.get
    def runtime(adapter):
        provider = get(adapter)
        def invoke(request):
            requests.append((adapter, request))
            payload = {'planner': {'tasks': [{'id': 'T1'}]},
                       'implementer': {'output': 'edited'},
                       'reviewer': {'approved': True, 'findings': []}}[request.role]
            return InvocationResult(text=json.dumps(payload))
        provider.invoke = invoke
        return provider
    registry.get = runtime
    selection = validate_preset(preset_id, registry=registry, choices={
        'impl': {'provider_config_id': 'custom-config', 'model': 'chosen-model',
                 'permission': 'workspace_write'}}, provider_configs={'custom-config': 'custom'})
    def agent(context):
        request = InvocationRequest(role=context.step.role, prompt=context.step.id, cwd='/fake/worktree',
                                    model=context.binding.model, permission=context.binding.permission)
        return json.loads(registry.get(context.adapter).invoke(request).text)
    graph = compile_workflow(selection.definition, selection.bindings,
                             provider_configs=selection.provider_configs, registry=registry,
                             executors={'plan': agent, 'implement': agent, 'review': agent,
                                        'test': lambda context: {'passed': True}})
    assert graph.invoke({})['status'] == 'ready_for_human_review'
    assert [adapter for adapter, _ in requests] == ['claude_code', 'custom',
                                                  'antigravity' if preset_id == 'default-v2' else 'codex_cli']
    assert requests[1][1].model == 'chosen-model'
    assert requests[1][1].permission == 'workspace_write'


@pytest.mark.parametrize('planner,implementer', [('claude', 'claude'), ('antigravity', 'antigravity')])
def test_cli_run_still_uses_legacy_path_by_default(tmp_path, monkeypatch, capsys, planner, implementer):
    from orchestrator import cli, core
    for key in ('ORCH_PLANNER', 'ORCH_IMPLEMENTER', 'ORCH_PLANNER_MODEL',
                'ORCH_IMPLEMENTER_MODEL', 'AGENT_TIMEOUT'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('ORCH_PLANNER', planner)
    monkeypatch.setenv('ORCH_IMPLEMENTER', implementer)
    scope = tmp_path / 'scope.md'
    scope.write_text('Example scope')
    seen = []
    monkeypatch.setattr(core, 'prepare', lambda repo, run_id: tmp_path)
    monkeypatch.setattr(core, 'repository_lock', lambda repo: nullcontext())
    monkeypatch.setattr(core, 'event', lambda *args: None)
    def invoke(state, entry_point):
        seen.append(AgentBindings.model_validate(state['bindings']))
        assert entry_point == 'plan'
        assert state['scope'] == 'Example scope'
        return {**state, 'status': 'ready_for_human_review'}
    monkeypatch.setattr(core, '_invoke', invoke)
    monkeypatch.setattr('sys.argv', ['orch', 'run', '--repo', str(tmp_path), '--scope', str(scope)])
    cli.main()
    assert seen == [legacy_bindings()]
    assert seen[0].preset == get_default_preset('cli').id
    assert json.loads(capsys.readouterr().out)['status'] == 'ready_for_human_review'
