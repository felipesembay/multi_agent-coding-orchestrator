from copy import deepcopy

import pytest
from pydantic import ValidationError

from orchestrator.workflows.schema import WorkflowDefinition



def test_round_trip_and_json_schema(definition):
    parsed = WorkflowDefinition.model_validate(definition)
    assert WorkflowDefinition.model_validate_json(parsed.model_dump_json()) == parsed
    assert 'discriminator' in WorkflowDefinition.model_json_schema()['properties']['steps']['items']


@pytest.mark.parametrize('path,value', [
    (('schema_version',), 2), (('schema_version',), True),
    (('name',), ''), (('limits', 'max_total_steps'), 0),
    (('limits', 'max_duration_s'), 86401), (('limits', 'budget_usd'), -1),
    (('limits', 'budget_usd'), float('nan')), (('limits', 'budget_usd'), float('inf')),
    (('limits', 'max_total_steps'), '200'), (('approval', 'require_tests'), 'true'),
    (('steps', 1, 'max_attempts'), 0), (('steps', 1, 'max_attempts'), 21),
    (('steps', 1, 'max_attempts'), True), (('steps', 1, 'role'), 'reviewer'),
    (('steps', 0, 'requires'), ['imaginary']), (('steps', 2, 'command_profile'), 'rm -rf .'),
    (('steps', 0, 'unexpected'), 1), (('limits', 'unexpected'), 1),
    (('approval', 'unexpected'), 1), (('unexpected',), 1),
    (('steps', 1, 'next'), 'plan'), (('steps', 0, 'per_task'), True),
    (('steps', 0, 'per_task'), 0),
])
def test_invalid_fields(definition, path, value):
    target = definition
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate(definition)


@pytest.mark.parametrize('change', [
    'empty', 'no_plan', 'second_plan', 'duplicate_id', 'split_block', 'missing_target',
    'forward_edge', 'outside_block', 'unbounded_target', 'tests_disabled',
    'tests_missing', 'review_missing',
])
def test_invalid_topology(definition, change):
    steps = definition['steps']
    if change == 'empty':
        definition['steps'] = []
    elif change == 'no_plan':
        steps.pop(0)
    elif change == 'second_plan':
        extra = deepcopy(steps[0]); extra['id'] = 'plan2'; steps.append(extra)
    elif change == 'duplicate_id':
        steps[2]['id'] = 'impl'
    elif change == 'split_block':
        steps.insert(2, {'id': 'gate', 'type': 'human_gate'})
    elif change == 'missing_target':
        steps[3]['on_reject'] = 'absent'
    elif change == 'forward_edge':
        steps[3]['on_reject'] = 'review'
    elif change == 'outside_block':
        steps[1]['per_task'] = False
    elif change == 'unbounded_target':
        steps[3]['on_reject'] = 'tests'
    elif change == 'tests_disabled':
        definition['approval']['require_tests'] = False
    elif change == 'tests_missing':
        steps.pop(2)
    elif change == 'review_missing':
        steps.pop(3)
    with pytest.raises(ValidationError) as error:
        WorkflowDefinition.model_validate(definition)
    assert error.value.errors()[0]['loc']  # usable by the future HTTP 422 handler


def test_optional_steps_and_gates(definition):
    definition['steps'].insert(1, {'id': 'gate', 'type': 'human_gate'})
    definition['steps'].append({'id': 'docs', 'type': 'document', 'role': 'documenter',
                                'requires': ['text']})
    definition['approval']['human_gate_after_plan'] = True
    assert len(WorkflowDefinition.model_validate(definition).steps) == 6


def test_boundary_limits(definition):
    definition['steps'][1]['max_attempts'] = 20
    definition['limits'] = {'max_total_steps': 10000, 'max_duration_s': 86400, 'budget_usd': 0}
    WorkflowDefinition.model_validate(definition)
