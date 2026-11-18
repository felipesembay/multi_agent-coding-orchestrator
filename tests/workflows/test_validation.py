from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from orchestrator.providers.base import Capability, CapabilityManifest
from orchestrator.providers.registry import ProviderRegistry
from orchestrator.workflows.schema import StepBinding, WorkflowDefinition
from orchestrator.workflows.validation import validate_workflow


@pytest.fixture
def setup(definition):
    manifest = CapabilityManifest(
        adapter='fake', kind='agent_runtime',
        capabilities=['text', 'planning', 'code_edit', 'review', 'structured_output'],
        permission_modes=['read_only', 'workspace_write'], auth_modes=['none'],
        billing_mode='local', usage_source='none', verified=True,
    )
    # Any attempt to execute, discover, or probe a provider fails the test.
    class FakeRegistry:
        def get(self, adapter):
            if adapter != manifest.adapter:
                raise KeyError(adapter)
            return SimpleNamespace(manifest=manifest)

    return dict(
        definition=definition,
        bindings={
            'plan': {'provider_config_id': 'pc-fake'},
            'impl': {'provider_config_id': 'pc-fake', 'permission': 'workspace_write'},
            'review': {'provider_config_id': 'pc-fake'},
        },
        provider_configs={'pc-fake': 'fake'}, registry=FakeRegistry(),
    ), manifest


def test_valid_bindings_and_round_trip(setup):
    args, _ = setup
    args['bindings']['plan']['model'] = 'chosen-model'
    args['bindings']['plan']['parameters'] = {'temperature': 0.2, 'nested': {'flag': True}}
    args['bindings']['plan']['fallbacks'] = [
        {'provider_config_id': 'pc-fake', 'model': 'backup', 'on': ['quota_exhausted', 'unavailable']},
    ]
    result = validate_workflow(**args)
    assert result.name == 'sample'
    assert 'bindings' not in result.model_dump()
    parsed = StepBinding.model_validate(args['bindings']['plan'])
    assert StepBinding.model_validate_json(parsed.model_dump_json()) == parsed


@pytest.mark.parametrize('change', [
    'missing_binding', 'extra_binding', 'test_binding', 'unknown_config', 'unknown_adapter',
    'missing_capability', 'omitted_required_capability', 'unverified', 'model_editor',
    'planner_write', 'reviewer_write', 'implementer_read', 'permission_unsupported',
    'invalid_manifest', 'identity_mismatch', 'fallback_unverified', 'fallback_permission',
    'fallback_capability', 'fallback_unknown', 'fallback_model_editor',
])
def test_invalid_binding_rules(setup, change):
    args, manifest = setup
    bindings = args['bindings']
    if change == 'missing_binding':
        del bindings['impl']
    elif change == 'extra_binding':
        bindings['typo'] = bindings['plan']
    elif change == 'test_binding':
        bindings['tests'] = bindings['plan']
    elif change == 'unknown_config':
        bindings['plan']['provider_config_id'] = 'missing'
    elif change == 'unknown_adapter':
        args['provider_configs']['pc-fake'] = 'missing'
    elif change == 'missing_capability':
        args['definition']['steps'][0]['requires'].append('streaming')
    elif change == 'omitted_required_capability':
        args['definition']['steps'][1]['requires'] = []
        manifest.capabilities.remove('code_edit')
    elif change == 'unverified':
        manifest.verified = False
    elif change == 'model_editor':
        manifest.kind = 'model_provider'
    elif change == 'planner_write':
        bindings['plan']['permission'] = 'workspace_write'
    elif change == 'reviewer_write':
        bindings['review']['permission'] = 'workspace_write'
    elif change == 'implementer_read':
        bindings['impl']['permission'] = 'read_only'
    elif change == 'permission_unsupported':
        manifest.permission_modes = ['read_only']
    elif change == 'invalid_manifest':
        manifest.kind = 'invalid'
    elif change == 'identity_mismatch':
        manifest.adapter = 'other'
    elif change.startswith('fallback_'):
        fallback_manifest = manifest.model_copy(deep=True)
        fallback_manifest.adapter = 'backup'
        args['provider_configs']['pc-backup'] = 'backup'
        old_get = args['registry'].get
        args['registry'].get = lambda adapter: SimpleNamespace(manifest=fallback_manifest) if adapter == 'backup' else old_get(adapter)
        bindings['impl']['fallbacks'] = [{'provider_config_id': 'pc-backup',
                                        'permission': 'workspace_write', 'on': ['rate_limited']}]
        if change == 'fallback_unverified':
            fallback_manifest.verified = False
        elif change == 'fallback_permission':
            del bindings['impl']['fallbacks'][0]['permission']
        elif change == 'fallback_capability':
            # Still meets implement requirements, but is weaker than primary.
            fallback_manifest.capabilities.remove('structured_output')
        elif change == 'fallback_unknown':
            bindings['impl']['fallbacks'][0]['provider_config_id'] = 'missing'
        elif change == 'fallback_model_editor':
            fallback_manifest.kind = 'model_provider'
    with pytest.raises(ValidationError) as error:
        validate_workflow(**args)
    assert error.value.errors()[0]['loc'][0] == 'bindings'


@pytest.mark.parametrize('fallback', [
    {'provider_config_id': 'pc-fake', 'on': []},
    {'provider_config_id': 'pc-fake', 'on': ['auth_failed']},
    {'provider_config_id': 'pc-fake', 'on': ['timeout']},
    {'provider_config_id': 'pc-fake', 'on': ['unavailable', 'unavailable']},
    {'provider_config_id': 'pc-fake', 'on': ['unavailable'], 'fallbacks': []},
    {'provider_config_id': 'pc-fake', 'on': ['unavailable'], 'unexpected': True},
])
def test_invalid_fallback_schema(setup, fallback):
    args, _ = setup
    args['bindings']['plan']['fallbacks'] = [fallback]
    with pytest.raises(ValidationError):
        validate_workflow(**args)


def test_model_provider_can_plan_and_review(setup):
    args, manifest = setup
    manifest.kind = 'model_provider'
    manifest.capabilities = {Capability.TEXT, Capability.PLANNING, Capability.REVIEW}
    manifest.permission_modes = ['read_only']
    # Text-only workflow is valid when approval policy agrees.
    args['definition']['steps'] = [args['definition']['steps'][0], args['definition']['steps'][3]]
    args['definition']['steps'][1].pop('on_reject')
    args['definition']['approval']['require_tests'] = False
    del args['bindings']['impl']
    validate_workflow(**args)


def test_builtin_manifest_not_bypassed_by_legacy_name(setup):
    args, _ = setup
    args['definition']['name'] = 'legacy-v1'
    args['registry'] = ProviderRegistry()
    args['provider_configs'] = {'pc-fake': 'antigravity'}
    with pytest.raises(ValidationError):
        validate_workflow(**args)


def test_revalidates_mutated_definition(setup):
    args, _ = setup
    model = WorkflowDefinition.model_validate(args['definition'])
    model.steps[1].max_attempts = 0
    args['definition'] = model
    with pytest.raises(ValidationError):
        validate_workflow(**args)


def test_definition_and_inputs_are_not_mutated(setup):
    args, _ = setup
    before = deepcopy((args['definition'], args['bindings'], args['provider_configs']))
    validate_workflow(**args)
    assert before == (args['definition'], args['bindings'], args['provider_configs'])


@pytest.mark.parametrize('value', [None, [], 'invalid', {'plan': {'provider_config_id': 'pc-fake', 'unknown': 1}}])
def test_invalid_binding_payload_has_field_error(setup, value):
    args, _ = setup
    args['bindings'] = value
    with pytest.raises(ValidationError) as error:
        validate_workflow(**args)
    assert error.value.errors()[0]['loc'][0] == 'bindings'


def test_plugin_manifest_failure_is_static(setup):
    args, _ = setup
    def failed_get(adapter):
        raise RuntimeError('sensitive plugin content')
    args['registry'].get = failed_get
    with pytest.raises(ValidationError) as error:
        validate_workflow(**args)
    assert 'sensitive' not in str(error.value)


def test_document_write_needs_verified_runtime(setup):
    args, manifest = setup
    # This manifest still serves read-only plan/review; writing documents must
    # not bypass code_edit verification just by omitting `requires`.
    manifest.verified = False
    args['definition']['steps'] = [args['definition']['steps'][0],
                                  {'id': 'docs', 'type': 'document'}]
    args['definition']['approval'].update(require_tests=False, require_reviewer=False)
    args['bindings'] = {'plan': args['bindings']['plan'],
                        'docs': {'provider_config_id': 'pc-fake', 'permission': 'workspace_write'}}
    with pytest.raises(ValidationError) as error:
        validate_workflow(**args)
    assert error.value.errors()[0]['loc'] == ('bindings', 'docs', 'permission')
    manifest.verified = True
    validate_workflow(**args)
