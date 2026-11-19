"""Read-only system templates and independent user workflow drafts.

Catalog access never reads the environment, discovers providers, seeds a DB or
executes agents. Every lookup builds fresh data; modifying a returned copy never
changes the system preset. Validation always uses authoritative catalog data.
"""
from typing import Literal, Mapping, Optional

from pydantic import BaseModel, Field, TypeAdapter

from ..providers.bindings import legacy_bindings, validate_bindings
from .schema import StepBinding, WorkflowDefinition
from .validation import validate_workflow


DEFAULT_CLI_PRESET = 'legacy-v1'
DEFAULT_UI_PRESET = 'default-v2'
_PRESET_IDS = ('legacy-v1', 'default-v2', 'openrouter-plan', 'claude-heavy')


class WorkflowConfiguration(BaseModel):
    """A clone has no trusted system identity or legacy execution marker.

    provider_configs contains logical template references, not persisted rows;
    the future host must map them to enabled configuration records. Validate
    against its registry before compilation/execution.
    """
    model_config = {'extra': 'forbid'}
    definition: WorkflowDefinition
    bindings: dict[str, StepBinding]
    provider_configs: dict[str, str]


class SystemPreset(BaseModel):
    model_config = {'extra': 'forbid', 'frozen': True}
    id: Literal['legacy-v1', 'default-v2', 'openrouter-plan', 'claude-heavy']
    title: str
    read_only: Literal[True] = True
    execution_mode: Literal['legacy', 'workflow']
    workflow: Optional[WorkflowConfiguration] = None
    blocked_by: tuple[str, ...] = Field(default_factory=tuple)


class PresetUnavailableError(ValueError):
    pass


def _definition(name):
    return WorkflowDefinition.model_validate({
        'schema_version': 1, 'name': name,
        'steps': [
            {'id': 'plan', 'type': 'plan', 'requires': ['planning', 'structured_output']},
            {'id': 'impl', 'type': 'implement', 'requires': ['code_edit'],
             'per_task': True, 'max_attempts': 3},
            {'id': 'tests', 'type': 'test', 'per_task': True, 'command_profile': 'server_default'},
            {'id': 'review', 'type': 'review', 'requires': ['review', 'structured_output'],
             'per_task': True, 'on_reject': 'impl'},
        ],
    })


def get_preset(preset_id: str) -> SystemPreset:
    if preset_id not in _PRESET_IDS:
        raise ValueError('Unknown workflow preset')
    if preset_id == 'legacy-v1':
        # Combined legacy review/test and fallback cannot be represented as a
        # strict v2 definition without changing behavior. Keep explicit metadata.
        return SystemPreset(id=preset_id, title='Legacy v1', execution_mode='legacy')
    references = {'pc-claude': 'claude_code', 'pc-codex': 'codex_cli', 'pc-agy': 'antigravity'}
    primary = {
        'default-v2': ('pc-claude', 'pc-codex', 'pc-agy'),
        'openrouter-plan': ('pc-openrouter', 'pc-codex', 'pc-claude'),
        'claude-heavy': ('pc-claude', 'pc-claude', 'pc-codex'),
    }[preset_id]
    if preset_id == 'openrouter-plan':
        references['pc-openrouter'] = 'openrouter'
    bindings = {step: StepBinding(provider_config_id=ref,
                                 permission='workspace_write' if step == 'impl' else 'read_only')
                for step, ref in zip(('plan', 'impl', 'review'), primary)}
    return SystemPreset(
        id=preset_id, title=preset_id, execution_mode='workflow',
        workflow=WorkflowConfiguration(definition=_definition(preset_id), bindings=bindings,
                                       provider_configs={ref: references[ref] for ref in primary}),
        blocked_by=(),
    )


def list_presets() -> list[SystemPreset]:
    return [get_preset(preset_id) for preset_id in _PRESET_IDS]


def get_default_preset(interface: Literal['cli', 'ui']) -> SystemPreset:
    if interface not in ('cli', 'ui'):
        raise ValueError('Unknown preset interface')
    return get_preset(DEFAULT_CLI_PRESET if interface == 'cli' else DEFAULT_UI_PRESET)


def clone_preset(preset_id: str, *, name: str, choices=None,
                 provider_configs: Optional[Mapping[str, str]] = None,
                 environ: Optional[Mapping[str, str]] = None) -> WorkflowConfiguration:
    """Create a strict, editable draft. This does not enable or execute a preset.

    choices replaces whole step bindings (never inherits write permission),
    provider_configs supplies trusted host mappings for new configuration IDs.
    A legacy clone uses primary roles only, a read-only planner and separate
    tests/review; the original legacy fallback remains exclusive to the CLI.
    """
    preset = get_preset(preset_id)
    if preset.execution_mode == 'legacy':
        legacy = legacy_bindings(environ)
        bindings = {}
        references = {}
        for step, role in (('plan', 'planner'), ('impl', 'implementer'), ('review', 'reviewer')):
            old = getattr(legacy, role)
            reference = f'pc-legacy-{step}'
            references[reference] = old.adapter
            # Empty legacy model strings are preserved by the original CLI,
            # but a new strict draft uses None (CLI default) instead. Explicit
            # choices are applied below without being blocked by that old value.
            bindings[step] = StepBinding(provider_config_id=reference, model=old.model or None,
                                         permission='workspace_write' if step == 'impl' else 'read_only')
        workflow = WorkflowConfiguration(definition=_definition(name), bindings=bindings,
                                         provider_configs=references)
    else:
        workflow = preset.workflow
    body = workflow.definition.model_dump()
    body['name'] = name
    workflow.definition = WorkflowDefinition.model_validate(body)
    if choices is not None:
        raw = ({key: value.model_dump() if isinstance(value, StepBinding) else value
                for key, value in choices.items()} if isinstance(choices, Mapping) else choices)
        parsed = TypeAdapter(dict[str, StepBinding]).validate_python(raw)
        if set(parsed) - set(workflow.bindings):
            raise ValueError('Preset choices must reference agent steps')
        workflow.bindings.update(parsed)
    if provider_configs is not None:
        workflow.provider_configs.update(TypeAdapter(dict[str, str]).validate_python(provider_configs))
    return workflow


def validate_preset(preset_id: str, *, registry, choices=None,
                    provider_configs: Optional[Mapping[str, str]] = None,
                    environ: Optional[Mapping[str, str]] = None):
    """Validate a system selection, without relaxing actual provider manifests.

    Returns AgentBindings for the existing legacy host, WorkflowConfiguration
    for strict workflows. Only IDs from this catalog select a system path;
    names in user definitions/clones never select legacy compatibility.
    """
    preset = get_preset(preset_id)
    if preset.blocked_by:
        raise PresetUnavailableError('Preset requires ' + ', '.join(preset.blocked_by))
    if preset.execution_mode == 'legacy':
        if choices is not None or provider_configs is not None:
            raise ValueError('Use clone_preset to customize a legacy workflow')
        return validate_bindings(legacy_bindings(environ), registry)
    workflow = clone_preset(preset_id, name=preset.workflow.definition.name,
                            choices=choices, provider_configs=provider_configs)
    validate_workflow(workflow.definition, workflow.bindings,
                      provider_configs=workflow.provider_configs, registry=registry)
    return workflow
