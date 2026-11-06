"""One managed workflow per process; the worker supervises the whole process group."""
import argparse
import json
import os
import time
from pathlib import Path

from . import core, projects
from .execution_manager import validate_configuration, validate_repository
from .project_store import connection


def run(run_id):
    # Spawn/registration handshake closes the crash window before PID persistence.
    row = None
    for _ in range(100):
        with connection() as conn:
            found = conn.execute('SELECT * FROM managed_runs WHERE run_id=?', (run_id,)).fetchone()
            row = dict(found) if found else None
        if not row or row['status'] != 'running' or row['dispatch_token'] != os.environ.get('ORCH_DISPATCH_TOKEN') or row['worker_id'] != os.environ.get('ORCH_WORKER_ID'):
            raise RuntimeError('Despacho inválido')
        if row['pid'] == os.getpid():
            break
        time.sleep(.1)
    else:
        raise RuntimeError('Worker não confirmou a inicialização')
    result = None
    try:
        config = json.loads(row['config'])
        validate_configuration(config)
        project = projects.get_project(row['project_id'])
        if project['state'] != 'active' or project['repo_path'] != row['repo']:
            raise projects.ProjectError('Projeto arquivado ou repositório alterado após o despacho.', 409)
        if validate_repository(project) != row['repo_identity']:
            raise projects.ProjectError('Identidade do repositório mudou. Nova confirmação necessária.', 409)
        mapping = {'ORCH_PLANNER': 'planner', 'ORCH_IMPLEMENTER': 'implementer',
                   'ORCH_TEST_COMMAND': 'test_command', 'MAX_ATTEMPTS': 'max_attempts',
                   'AGENT_TIMEOUT': 'agent_timeout', 'TEST_TIMEOUT': 'test_timeout',
                   'ORCH_WORKTREES': 'worktree_base'}
        for env_key, config_key in mapping.items():
            os.environ[env_key] = str(config[config_key])
        os.environ['ORCH_PLANNER_MODEL'] = config['planner_model'] or config['planner_fallback_model']
        if config['implementer_model']:
            os.environ['ORCH_IMPLEMENTER_MODEL'] = config['implementer_model']
        else:
            os.environ.pop('ORCH_IMPLEMENTER_MODEL', None)
        # Worktree path comes only from server policy and the server-generated run ID.
        expected = Path(config['worktree_base']) / run_id
        projects.authorized_path(str(expected))
        result = core.execute_scope(row['repo'], row['scope'], run_id=run_id, managed=True)
        saved = {key: result.get(key) for key in ('status', 'worktree', 'task_index', 'review')}
        with connection() as conn:
            conn.execute('UPDATE managed_runs SET result=?,worktree=? WHERE run_id=?', (json.dumps(saved), result.get('worktree'), run_id))
            conn.commit()
    except Exception as exc:
        # Agent exceptions are already audited by core; preflight failures need an event too.
        message = ('Worker: ' + str(exc))[-2500:]
        core.event({'run_id': run_id}, 'manager_error', {'message': message})
        with connection() as conn:
            conn.execute('UPDATE managed_runs SET result=?,error=? WHERE run_id=?', (json.dumps({'status': 'failed'}), message, run_id))
            conn.commit()
        return 1
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    raise SystemExit(run(parser.parse_args().run_id))
