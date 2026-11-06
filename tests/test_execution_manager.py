import json
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from orchestrator import core, execution_manager as manager, projects
from orchestrator.api import app
from orchestrator.project_store import connection
from orchestrator.repository_lock import repository_lock, lock_fd
from orchestrator.worker import Worker, reconcile, group_members


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path / 'projects'
    root.mkdir()
    monkeypatch.setenv('ORCH_DB', str(tmp_path / 'events.db'))
    monkeypatch.setenv('ORCH_ALLOWED_ROOTS', str(root))
    monkeypatch.setenv('ORCH_TEST_COMMAND', f'{sys.executable} -m pytest -q')
    monkeypatch.setenv('ORCH_ALLOWED_TEST_COMMANDS', json.dumps([[sys.executable, '-m', 'pytest', '-q']]))
    monkeypatch.setenv('ORCH_PLANNER', 'claude')
    monkeypatch.setenv('ORCH_IMPLEMENTER', 'antigravity')
    monkeypatch.delenv('ORCH_WORKTREES', raising=False)
    which = manager.shutil.which
    monkeypatch.setattr(manager.shutil, 'which', lambda name: sys.executable if name in ('claude', 'agy', 'codex') else which(name))
    preview = projects.preview(projects.ProjectInput(name='Task Manager API', repo_path=str(root / 'tasks'), mode='create'))
    project = projects.create(projects.ProjectConfirmation(preview_token=preview['preview_token'], confirmed=True))
    request = projects.submit_request(project['id'], projects.RequestInput(title='Criar API de tarefas', content='Criar uma API REST para gerenciar tarefas pessoais.'))
    worker = Worker()
    worker.heartbeat()
    with TestClient(app, base_url='http://127.0.0.1:8765', client=('127.0.0.1', 50000)) as client:
        csrf = client.get('/session').json()['csrf_token']
        client.headers.update({'Origin': 'http://127.0.0.1:5173', 'X-Orchestrator-CSRF': csrf})
        yield client, project, request, worker


def body(project, key='idempotency-key-one'):
    return dict(confirmed=True, configuration_digest=manager.configuration(project)[1], idempotency_key=key)


def url(project, request):
    return f"/projects/{project['id']}/requests/{request['id']}/runs"


def test_queued_persisted_link_idempotency_and_no_agents_in_http(setup, monkeypatch):
    client, project, request, _ = setup
    agent = Mock(side_effect=AssertionError('HTTP must not invoke agents'))
    monkeypatch.setattr(core, 'execute_scope', agent)
    response = client.post(url(project, request), json=body(project))
    assert response.status_code == 202, response.text
    run = response.json()
    assert run['status'] == 'queued'
    assert client.post(url(project, request), json=body(project)).json()['run_id'] == run['run_id']
    assert not agent.called
    detail = client.get('/runs/' + run['run_id']).json()
    assert detail['project_name'] == project['name']
    assert detail['request_title'] == request['title']
    assert detail['status'] == 'queued'
    assert detail['events'] == []
    assert 'dispatch_token' not in detail
    assert 'scope' not in detail
    assert client.get(f"/projects/{project['id']}/runs?linked_only=true").json()[0]['run_id'] == run['run_id']
    assert client.get('/overview').json()['counts']['queued'] == 1
    with TestClient(app) as fresh:
        assert fresh.get('/runs/' + run['run_id']).json()['request_id'] == request['id']


def test_missing_project_request_and_cross_project(setup):
    client, project, request, _ = setup
    assert client.post('/projects/missing/requests/missing/runs', json=body(project)).status_code == 404
    assert client.post(f"/projects/{project['id']}/requests/missing/runs", json=body(project)).status_code == 404
    with connection() as conn:
        conn.execute('INSERT INTO projects(id,name,description,objectives,repository_id) VALUES(?,?,?,?,?)', ('other', 'Other', '', '', project['repository_id']))
        conn.commit()
    assert client.post(f"/projects/other/requests/{request['id']}/runs", json=body(project)).status_code == 409


def test_repository_authorization_invalid_git_and_dirty_repo(setup, monkeypatch):
    client, project, request, _ = setup
    (Path(project['repo_path']) / 'uncommitted.txt').write_text('uncommitted')
    assert client.post(url(project, request), json=body(project)).status_code == 409
    (Path(project['repo_path']) / 'uncommitted.txt').unlink()
    (Path(project['repo_path']) / '.git').rename(Path(project['repo_path']) / '.git-hidden')
    assert client.post(url(project, request), json=body(project)).status_code == 422
    monkeypatch.setenv('ORCH_ALLOWED_ROOTS', '/tmp/different-allowed-root')
    assert client.post(url(project, request), json=body(project)).status_code == 403


def test_worker_offline_and_invalid_config(setup, monkeypatch):
    client, project, request, _ = setup
    with connection() as conn:
        conn.execute('DELETE FROM execution_worker')
        conn.commit()
    assert client.post(url(project, request), json=body(project)).status_code == 503
    assert client.get(f"/projects/{project['id']}/execution-config").json()['ready'] is False
    monkeypatch.setenv('ORCH_IMPLEMENTER', 'unsupported')
    assert client.post(url(project, request), json=body(project)).status_code == 422


def test_stale_configuration_and_arbitrary_browser_commands_rejected(setup, monkeypatch):
    client, project, request, _ = setup
    original = body(project)
    monkeypatch.setenv('ORCH_PLANNER', 'antigravity')
    assert client.post(url(project, request), json=original).status_code == 409
    extra = dict(body(project), test_command='sh -c evil')
    assert client.post(url(project, request), json=extra).status_code == 422
    monkeypatch.setenv('ORCH_TEST_COMMAND', 'sh -c evil')
    assert client.post(url(project, request), json=body(project)).status_code == 422


def test_concurrent_submissions_reserve_underlying_repository(setup):
    client, project, request, _ = setup
    def submit(i):
        try:
            return manager.submit(project['id'], request['id'], manager.StartInput(**body(project, f'concurrent-key-{i:04}')))
        except projects.ProjectError as exc:
            return exc.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sum(isinstance(r, dict) for r in results) == 1
    assert 409 in results
    with repository_lock(project['repo_path']):
        assert client.get(f"/projects/{project['id']}/execution-config").json()['ready'] is False


def test_spawn_failure_is_persisted(setup, monkeypatch):
    client, project, request, worker = setup
    run_id = client.post(url(project, request), json=body(project)).json()['run_id']
    monkeypatch.setattr(worker, 'spawn', Mock(side_effect=OSError('spawn failed')))
    assert worker.run_once()
    detail = client.get('/runs/' + run_id).json()
    assert detail['status'] == 'failed'
    assert 'supervisionar' in detail['error']
    assert detail['finished_at']


def test_supervised_real_graph_worktree_tests_and_mocked_agents(setup, monkeypatch):
    client, project, request, worker = setup
    run_id = client.post(url(project, request), json=body(project)).json()['run_id']
    def spawn(row):
        env = dict(os.environ, ORCH_DB=core.db_path(), ORCH_WORKER_ID=worker.id, ORCH_DISPATCH_TOKEN=row['dispatch_token'])
        return subprocess.Popen([sys.executable, str(Path(__file__).parent / 'fixtures/managed_workflow.py'), row['run_id']], env=env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    monkeypatch.setattr(worker, 'spawn', spawn)
    assert worker.run_once()
    result = client.get('/runs/' + run_id).json()
    assert result['status'] == 'ready_for_human_review', result
    assert result['tests_passed'] is True
    assert result['task_count'] == 1
    assert result['attempts'] == 1
    assert Path(result['worktree'], 'calculator.py').exists()
    assert not Path(project['repo_path'], 'calculator.py').exists()
    events = client.get('/runs/' + run_id + '/events').json()
    assert [event['stage'] for event in events if event['stage'] != 'stage_started'] == ['started', 'plan', 'implementation', 'review', 'finished']
    assert len([e for e in events if e['stage'] == 'stage_started']) == 3
    assert client.get('/runs/' + run_id).json()['request_id'] == request['id']


def test_recovery_marks_interrupted_without_replaying_and_allows_explicit_new_run(setup):
    client, project, request, worker = setup
    old = client.post(url(project, request), json=body(project)).json()['run_id']
    worker.claim()  # Crash before the child registration handshake.
    reconcile()
    assert client.get('/runs/' + old).json()['status'] == 'interrupted'
    assert client.get('/runs/' + old + '/events').json() == []
    assert client.post(url(project, request), json=body(project, 'explicit-new-run-key')).status_code == 202


def test_verified_orphan_process_is_terminated_before_releasing_reservation(setup):
    client, project, request, worker = setup
    run_id = client.post(url(project, request), json=body(project)).json()['run_id']
    row = worker.claim()
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True,
                             env=dict(os.environ, ORCH_DISPATCH_TOKEN=row['dispatch_token']))
    try:
        info = manager.process_identity(child.pid)
        with connection() as conn:
            conn.execute('UPDATE managed_runs SET pid=?,process_start=?,boot_id=? WHERE run_id=?', (child.pid, info['start'], manager.boot_id(), run_id))
            conn.commit()
        reconcile()
        child.wait(timeout=5)
        assert not group_members(child.pid)
        assert client.get('/runs/' + run_id).json()['status'] == 'interrupted'
        assert not client.get('/runs/' + run_id).json()['orphaned']
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()


def test_unverified_orphan_keeps_repository_reserved(setup, monkeypatch):
    client, project, request, worker = setup
    run_id = client.post(url(project, request), json=body(project)).json()['run_id']
    worker.claim()
    monkeypatch.setattr('orchestrator.worker.clean_group', lambda row: False)
    reconcile()
    assert client.get('/runs/' + run_id).json()['orphaned'] is True
    assert client.post(url(project, request), json=body(project, 'another-new-run-key')).status_code == 409


def test_cli_lock_is_inherited_by_running_tools(setup):
    _, project, _, _ = setup
    with repository_lock(project['repo_path']):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], pass_fds=(lock_fd.get(),))
    try:
        with pytest.raises(RuntimeError, match='Já existe'):
            with repository_lock(project['repo_path']):
                pass
    finally:
        child.kill()
        child.wait()


def test_recovery_does_not_signal_a_reused_unverified_process_group(setup, monkeypatch):
    from orchestrator import worker as worker_module
    client, project, request, worker = setup
    run_id = client.post(url(project, request), json=body(project)).json()['run_id']
    worker.claim()
    with connection() as conn:
        conn.execute('UPDATE managed_runs SET pid=?,process_start=?,boot_id=? WHERE run_id=?', (999999, 'old-start', manager.boot_id(), run_id))
        conn.commit()
    kill = Mock()
    monkeypatch.setattr(worker_module, 'group_members', lambda group: [999999])
    monkeypatch.setattr(worker_module, 'verified_group', lambda row: False)
    monkeypatch.setattr(worker_module.os, 'killpg', kill)
    reconcile()
    assert not kill.called
    assert client.get('/runs/' + run_id).json()['orphaned'] is True


@pytest.mark.parametrize('scope,expected', [('BLOCK_TESTS', 'blocked'), ('FAIL_PLANNER', 'failed')])
def test_graph_failure_and_blocked_results_are_not_misreported_as_success(setup, monkeypatch, scope, expected):
    client, project, request, worker = setup
    with connection() as conn:
        conn.execute('UPDATE project_requests SET content=? WHERE id=?', (scope, request['id']))
        conn.commit()
    run_id = client.post(url(project, request), json=body(project)).json()['run_id']
    def spawn(row):
        return subprocess.Popen([sys.executable, str(Path(__file__).parent / 'fixtures/managed_workflow.py'), row['run_id']],
                                env=dict(os.environ, ORCH_DB=core.db_path(), ORCH_WORKER_ID=worker.id, ORCH_DISPATCH_TOKEN=row['dispatch_token']),
                                start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    monkeypatch.setattr(worker, 'spawn', spawn)
    worker.run_once()
    result = client.get('/runs/' + run_id).json()
    assert result['status'] == expected, result
    if expected == 'blocked':
        assert result['tests_passed'] is False
        assert result['attempts'] == 3
    else:
        assert 'Mocked planner failure' in result['error']


def test_two_projects_cannot_execute_the_same_repository_concurrently(setup):
    client, project, request, _ = setup
    assert client.post(url(project, request), json=body(project)).status_code == 202
    with connection() as conn:
        conn.execute('INSERT INTO projects(id,name,description,objectives,repository_id) VALUES(?,?,?,?,?)', ('same-repo-project', 'Other project', '', '', project['repository_id']))
        conn.commit()
    other_project = projects.get_project('same-repo-project')
    other_request = projects.submit_request(other_project['id'], projects.RequestInput(title='Another task', content='Implement another task'))
    assert client.post(url(other_project, other_request), json=body(other_project, 'other-project-intent')).status_code == 409


def test_cli_resume_does_not_bypass_managed_lifecycle(setup):
    client, project, request, _ = setup
    run_id = client.post(url(project, request), json=body(project)).json()['run_id']
    with pytest.raises(ValueError, match='Execução gerenciada'):
        core.resume(run_id)
    assert client.get('/runs/' + run_id).json()['status'] == 'queued'


def test_worker_loss_is_visible_without_inventing_a_completed_state(setup):
    client, project, request, _ = setup
    run_id = client.post(url(project, request), json=body(project)).json()['run_id']
    with connection() as conn:
        conn.execute('DELETE FROM execution_worker')
        conn.commit()
    result = client.get('/runs/' + run_id).json()
    assert result['status'] == 'queued'
    assert result['supervisor_online'] is False
    assert result['finished_at'] is None
    assert result['events'] == []


def test_worker_without_directory_policy_reports_its_own_configuration_error(setup, monkeypatch):
    client, project, request, worker = setup
    run_id = client.post(url(project, request), json=body(project)).json()['run_id']
    def spawn(row):
        env = dict(os.environ, ORCH_DB=core.db_path(), ORCH_WORKER_ID=worker.id,
                   ORCH_DISPATCH_TOKEN=row['dispatch_token'])
        env.pop('ORCH_ALLOWED_ROOTS', None)
        return subprocess.Popen([sys.executable, str(Path(__file__).parent / 'fixtures/managed_workflow.py'), row['run_id']],
                                env=env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    monkeypatch.setattr(worker, 'spawn', spawn)
    worker.run_once()
    result = client.get('/runs/' + run_id).json()
    assert result['status'] == 'failed'
    assert result['error'].startswith('Worker: Diretório não autorizado.')
    assert 'ORCH_ALLOWED_ROOTS' in result['error']
    assert not Path(project['repo_path']).with_name('tasks-agent-worktrees').exists()
