"""Worker integration: mock agents, real Git/LangGraph and env assertions in pytest."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator import core, execution_runner
from managed_workflow import agent


def fake_agent(prompt, cwd, role, state=None):
    assert os.getenv('SENTINEL_SECRET') is None
    assert os.getenv('OPENAI_API_KEY') is None
    result = agent(prompt, cwd, role, state)
    if role == 'implementer':
        Path(cwd, 'test_environment.py').write_text('''import os

def test_subprocess_environment():
    assert os.getenv('SENTINEL_SECRET') is None
    assert os.getenv('OPENAI_API_KEY') is None
    assert os.getenv('ORCH_DB') is None
    assert os.getenv('ORCH_WORKER_ID') is None
    assert os.getenv('TEST_FIXTURE_DIR') == '/tmp/authorized-test-fixture'
    assert os.getenv('ORCH_DISPATCH_TOKEN')
''')
    return result


if __name__ == '__main__':
    with patch.object(core, 'coding_agent', side_effect=fake_agent), \
         patch.object(core, 'codex', return_value='{"approved":true,"findings":[]}'), \
         patch.object(execution_runner, 'validate_configuration'):
        raise SystemExit(execution_runner.run(sys.argv[1]))
