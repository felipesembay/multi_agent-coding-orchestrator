"""Pure validation with field paths, using only already-enabled providers.

provider_configs maps trusted configuration IDs to adapter IDs. Persistence and
API integration are later tasks; workflow input never loads plugins or probes.
"""
from typing import Mapping

from pydantic import TypeAdapter, ValidationError

from ..providers.base import Capability, CapabilityManifest
from .schema import AgentStep, StepBinding, WorkflowDefinition


def _issue(errors, location, message):
    errors.append({'type': 'value_error', 'loc': location, 'input': None,
                   'ctx': {'error': ValueError(message)}})


def _raise(errors):
    if errors:
        raise ValidationError.from_exception_data('Workflow validation', errors)


def validate_structure(definition: WorkflowDefinition):
    errors = []
    steps = definition.steps
    ids = {}
    for index, step in enumerate(steps):
        if step.id in ids:
            _issue(errors, ('steps', index, 'id'), 'Step IDs must be unique')
        ids[step.id] = index
        if (index == 0) != (step.type == 'plan'):
            _issue(errors, ('steps', index, 'type'), 'Exactly one plan must be first')
    per_task = [i for i, step in enumerate(steps) if step.per_task]
    if per_task and per_task != list(range(per_task[0], per_task[-1] + 1)):
        _issue(errors, ('steps',), 'per_task steps must form one contiguous block')
    for index, step in enumerate(steps):
        if step.type != 'review' or step.on_reject is None:
            continue
        target_index = ids.get(step.on_reject)
        if target_index is None or target_index >= index:
            _issue(errors, ('steps', index, 'on_reject'), 'Return target must be an earlier step')
            continue
        target = steps[target_index]
        if (not all(s.per_task for s in steps[target_index:index + 1])
                or target.type != 'implement'):
            _issue(errors, ('steps', index, 'on_reject'),
                   'Return must target a bounded implementation in the same per_task block')
    has_tests = any(s.type == 'test' for s in steps)
    if definition.approval.require_tests != has_tests:
        _issue(errors, ('approval', 'require_tests'), 'require_tests must match presence of test steps')
    if definition.approval.require_reviewer and not any(s.type == 'review' for s in steps):
        _issue(errors, ('approval', 'require_reviewer'), 'Required reviewer step is missing')
    _raise(errors)


def validate_workflow(definition, bindings, *, provider_configs: Mapping[str, str], registry) -> WorkflowDefinition:
    """Raise Pydantic ValidationError suitable for later HTTP 422 integration.

    No legacy-v1 exception: name alone cannot bypass verification/permissions.
    Fallback permission is explicit (default read_only), never inherited from a
    potentially more privileged primary. All fallbacks are checked up front.
    """
    # Reparse models too: callers may have mutated lists or used model_construct.
    definition = WorkflowDefinition.model_validate(
        definition.model_dump() if isinstance(definition, WorkflowDefinition) else definition)
    raw_bindings = ({key: value.model_dump() if isinstance(value, StepBinding) else value
                     for key, value in bindings.items()} if isinstance(bindings, Mapping) else bindings)
    try:
        parsed = TypeAdapter(dict[str, StepBinding]).validate_python(raw_bindings)
    except ValidationError as exc:
        details = exc.errors(include_url=False)
        for detail in details:
            detail['loc'] = ('bindings',) + detail['loc']
        raise ValidationError.from_exception_data('Workflow bindings', details) from None
    errors = []
    agent_steps = {s.id: s for s in definition.steps if isinstance(s, AgentStep)}
    for step_id in sorted(set(parsed) - set(agent_steps)):
        _issue(errors, ('bindings', step_id), 'Binding must reference an agent step')
    for step_id, step in agent_steps.items():
        if step_id not in parsed:
            _issue(errors, ('bindings', step_id), 'Agent step binding is required')
            continue
        binding = parsed[step_id]
        primary = _validate_provider(step, binding, ('bindings', step_id), provider_configs, registry, errors)
        for index, fallback in enumerate(binding.fallbacks):
            location = ('bindings', step_id, 'fallbacks', index)
            manifest = _validate_provider(step, fallback, location, provider_configs, registry, errors)
            if primary is not None and manifest is not None and not primary.capabilities <= manifest.capabilities:
                _issue(errors, location + ('provider_config_id',),
                       'Fallback capabilities must include all primary capabilities')
    _raise(errors)
    return definition


def _validate_provider(step, binding, location, configs, registry, errors):
    adapter = configs.get(binding.provider_config_id)
    if adapter is None:
        _issue(errors, location + ('provider_config_id',), 'Unknown provider configuration')
        return None
    try:
        provider = registry.get(adapter)
        raw = provider.manifest
        manifest = CapabilityManifest.model_validate(raw.model_dump() if isinstance(raw, CapabilityManifest) else raw)
        if manifest.adapter != adapter:
            raise ValueError('Identity mismatch')
    except Exception:
        # Plugin manifest properties can fail too. Do not surface their payloads.
        _issue(errors, location + ('provider_config_id',), 'Provider unavailable or invalid')
        return None
    # Required role capabilities cannot be removed by editing `requires`.
    minimum = {'plan': Capability.PLANNING, 'implement': Capability.CODE_EDIT,
               'review': Capability.REVIEW, 'document': Capability.TEXT}[step.type]
    required = set(step.requires) | {Capability.TEXT, minimum}
    if not required <= manifest.capabilities:
        _issue(errors, location + ('provider_config_id',), 'Provider lacks required step capabilities')
    if Capability.CODE_EDIT in required and (manifest.kind != 'agent_runtime' or not manifest.verified):
        _issue(errors, location + ('provider_config_id',), 'code_edit requires a verified agent_runtime')
    permission = binding.permission
    if step.role in ('planner', 'reviewer') and permission != 'read_only':
        _issue(errors, location + ('permission',), 'Planner and reviewer require read_only')
    if (step.role == 'implementer' or Capability.CODE_EDIT in required) and permission != 'workspace_write':
        _issue(errors, location + ('permission',), 'Editing requires workspace_write')
    if permission not in manifest.permission_modes:
        _issue(errors, location + ('permission',), 'Provider does not support permission')
    if permission == 'workspace_write' and (
            manifest.kind != 'agent_runtime' or not manifest.verified
            or Capability.CODE_EDIT not in manifest.capabilities):
        _issue(errors, location + ('permission',), 'Workspace writes require a verified code_edit runtime')
    if manifest.kind == 'model_provider' and permission != 'read_only':
        _issue(errors, location + ('permission',), 'Model providers cannot write the workspace')
    return manifest
