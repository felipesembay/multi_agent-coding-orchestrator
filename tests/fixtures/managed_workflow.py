"""Subprocess integration fixture: real LangGraph/Git/tests; agent calls mocked."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator import core, execution_runner


def agent(prompt, cwd, role, state=None):
    if role == 'planner':
        if 'FAIL_PLANNER' in state.get('scope', ''):
            raise RuntimeError('Mocked planner failure')
        instructions = 'BLOCK_TESTS' if 'BLOCK_TESTS' in state.get('scope', '') else 'Implement sum'
        return json.dumps({'tasks': [{'id': 'T1', 'title': 'Implement requested function',
                                    'instructions': instructions, 'acceptance': ['tests pass']}]})
    Path(cwd, 'calculator.py').write_text('def add(a, b):\n    return a - b\n' if 'BLOCK_TESTS' in prompt else 'def add(a, b):\n    return a + b\n')
    Path(cwd, 'test_calculator.py').write_text('from calculator import add\ndef test_add():\n    assert add(2, 3) == 5\n')
    return 'Created calculator and tests.'


if __name__ == '__main__':
    with patch.object(core, 'coding_agent', side_effect=agent), \
         patch.object(core, 'codex', return_value='{"approved":true,"findings":[],"test_suggestions":[]}'), \
         patch.object(execution_runner, 'validate_configuration'):
        raise SystemExit(execution_runner.run(sys.argv[1]))
