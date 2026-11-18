import pytest


@pytest.fixture
def definition():
    return {
        'schema_version': 1, 'name': 'sample',
        'steps': [
            {'id': 'plan', 'type': 'plan', 'role': 'planner', 'requires': ['planning']},
            {'id': 'impl', 'type': 'implement', 'role': 'implementer',
             'requires': ['code_edit'], 'per_task': True, 'max_attempts': 3},
            {'id': 'tests', 'type': 'test', 'per_task': True, 'command_profile': 'server_default'},
            {'id': 'review', 'type': 'review', 'role': 'reviewer', 'requires': ['review'],
             'per_task': True, 'on_reject': 'impl'},
        ],
        'limits': {'max_total_steps': 200, 'max_duration_s': 14400, 'budget_usd': None},
        'approval': {'require_tests': True, 'require_reviewer': True, 'human_gate_after_plan': False},
    }
