"""Browser integration harness, restricted to a temporary database; never real agents."""
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from orchestrator import core, projects
from orchestrator.execution_manager import validate_configuration
from orchestrator.worker import Worker


def mock_spawn(self, row):
    env = dict(os.environ, ORCH_DB=core.db_path(), ORCH_WORKER_ID=self.id, ORCH_DISPATCH_TOKEN=row['dispatch_token'])
    return subprocess.Popen([sys.executable, str(ROOT / 'tests/fixtures/managed_workflow.py'), row['run_id']],
                            env=env, start_new_session=True, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    state = Path(core.db_path()).resolve().parent
    if not str(state).startswith('/tmp/orchestrator-execution-qa.'):
        raise SystemExit('This fixture accepts only an isolated /tmp/orchestrator-execution-qa.* database')
    existing_which = shutil.which
    with patch('shutil.which', side_effect=lambda name: sys.executable if name in ('claude', 'agy', 'codex') else existing_which(name)):
        if sys.argv[1] == 'api':
            existing = projects.list_projects()
            if not existing:
                preview = projects.preview(projects.ProjectInput(name='Task Manager API (test)', repo_path=str(state / 'repositories/task_manager'), mode='create'))
                project = projects.create(projects.ProjectConfirmation(preview_token=preview['preview_token'], confirmed=True))
                projects.submit_request(project['id'], projects.RequestInput(title='Criar uma API REST para gerenciar tarefas pessoais.', content='Criar uma API REST para gerenciar tarefas pessoais.'))
            import uvicorn
            uvicorn.run('orchestrator.api:app', host='127.0.0.1', port=18765)
        elif sys.argv[1] == 'worker':
            with patch.object(Worker, 'spawn', mock_spawn):
                Worker().run()
        else:
            raise SystemExit('Expected api or worker')
