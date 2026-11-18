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
    with TestClient(app, base_url='http://127.0.0.1:8765', client=('127.0.0.1', 50000)) as fresh:
        fresh.headers['X-Orchestrator-CSRF'] = fresh.get('/session').json()['csrf_token']
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


@pytest.mark.parametrize('status,orphaned', [('queued', 0), ('running', 0), ('interrupted', 1)])
def test_delete_project_blocks_active_or_orphaned_execution(setup, status, orphaned):
    client, project, request, _ = setup
    run_id = client.post(url(project, request), json=body(project)).json()['run_id']
    with connection() as conn:
        conn.execute('UPDATE managed_runs SET status=?,orphaned=? WHERE run_id=?', (status, orphaned, run_id))
        conn.commit()
    response = client.request('DELETE', '/projects/' + project['id'], json={'confirmed': True, 'project_name': project['name']})
    assert response.status_code == 409
    assert client.get('/projects/' + project['id']).status_code == 200


@pytest.mark.parametrize('status', ['failed', 'interrupted', 'blocked', 'ready_for_human_review'])
def test_delete_finished_project_retains_execution_evidence_and_blocks_new_jobs(setup, status):
    client, project, request, _ = setup
    run_id = client.post(url(project, request), json=body(project)).json()['run_id']
    with connection() as conn:
        conn.execute('UPDATE managed_runs SET status=?,orphaned=0 WHERE run_id=?', (status, run_id))
        conn.commit()
    core.event({'run_id': run_id}, 'manager_error', {'message': 'Preserved evidence'})
    assert client.request('DELETE', '/projects/' + project['id'], json={'confirmed': True, 'project_name': project['name']}).status_code == 200
    detail = client.get('/runs/' + run_id).json()
    assert detail['project_deleted'] is True
    assert detail['status'] == status
    assert detail['events'][0]['stage'] == 'manager_error'
    assert client.post(url(project, request), json=body(project, 'new-intent-after-deletion')).status_code == 404
    assert client.post(url(project, request), json=body(project)).status_code == 404


def test_delete_and_submit_cannot_both_win_the_reservation_race(setup):
    _, project, request, _ = setup
    payload = manager.StartInput(**body(project))
    confirmation = projects.ProjectDeletion(confirmed=True, project_name=project['name'])
    def action(kind):
        try:
            if kind == 'submit':
                manager.submit(project['id'], request['id'], payload)
            else:
                projects.delete_project(project['id'], confirmation)
            return kind
        except projects.ProjectError as exc:
            return exc.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(action, ['submit', 'delete']))
    assert not ('submit' in results and 'delete' in results)
    assert 'submit' in results or 'delete' in results
    assert any(value in (404, 409) for value in results)


def test_legacy_configuration_shape_digest_and_preflight_are_preserved(setup, monkeypatch):
    import hashlib
    client, project, _, _ = setup
    monkeypatch.setenv('ORCH_PLANNER_MODEL', 'saved-fallback')
    monkeypatch.setenv('ORCH_IMPLEMENTER_MODEL', 'saved-implementer')
    monkeypatch.setenv('MAX_ATTEMPTS', '4')
    monkeypatch.setenv('AGENT_TIMEOUT', '71')
    monkeypatch.setenv('TEST_TIMEOUT', '51')
    expected = dict(planner='claude', implementer='antigravity', reviewer='codex',
        planner_model=None, implementer_model='saved-implementer', planner_fallback_model='saved-fallback',
        test_command=f'{sys.executable} -m pytest -q', max_attempts=4, agent_timeout=71, test_timeout=51,
        worktree_base=str(Path(project['repo_path']).parent / (Path(project['repo_path']).name + '-agent-worktrees')))
    config, digest = manager.configuration(project)
    assert config == expected
    assert digest == hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
    response = client.get(f"/projects/{project['id']}/execution-config").json()
    assert response['configuration'] == expected
    assert response['configuration_digest'] == digest
    monkeypatch.setenv('SENTINEL_API_SECRET', 'never-a-binding')
    assert manager.configuration(project) == (config, digest)


def test_explicit_bindings_are_serialized_digested_and_consistency_checked(setup):
    from orchestrator.providers.bindings import AgentBindings, bindings_from_snapshot, legacy_bindings
    _, project, _, _ = setup
    original = legacy_bindings()
    config, digest = manager.configuration(project, bindings=original)
    assert config['bindings'] == original.model_dump()
    assert bindings_from_snapshot(config) == original
    manager.validate_configuration(config)
    modified = original.model_dump()
    modified['implementer']['model'] = 'another-model'
    next_config, next_digest = manager.configuration(project, bindings=AgentBindings.model_validate(modified))
    assert next_digest != digest
    assert bindings_from_snapshot(next_config).implementer.model == 'another-model'
    inconsistent = dict(config, agent_timeout=config['agent_timeout'] + 1)
    with pytest.raises(projects.ProjectError, match='Bindings'):
        manager.validate_configuration(inconsistent)


def test_dispatch_uses_saved_bindings_despite_worker_environment_drift(setup, monkeypatch):
    client, project, request, worker = setup
    monkeypatch.setenv('ORCH_PLANNER_MODEL', 'frozen-fallback')
    monkeypatch.setenv('ORCH_IMPLEMENTER_MODEL', 'frozen-implementer')
    monkeypatch.setenv('AGENT_TIMEOUT', '83')
    run_id = client.post(url(project, request), json=body(project)).json()['run_id']
    with connection() as conn:
        before = conn.execute('SELECT config FROM managed_runs WHERE run_id=?', (run_id,)).fetchone()['config']
    def spawn(row):
        env = dict(os.environ, ORCH_DB=core.db_path(), ORCH_WORKER_ID=worker.id,
                   ORCH_DISPATCH_TOKEN=row['dispatch_token'], ORCH_PLANNER='unsupported',
                   ORCH_IMPLEMENTER='unsupported', ORCH_PLANNER_MODEL='drift',
                   ORCH_IMPLEMENTER_MODEL='drift', AGENT_TIMEOUT='1')
        return subprocess.Popen([sys.executable, str(Path(__file__).parent / 'fixtures/managed_workflow.py'), row['run_id']],
            env=env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    monkeypatch.setattr(worker, 'spawn', spawn)
    assert worker.run_once()
    detail = client.get('/runs/' + run_id).json()
    assert detail['status'] == 'ready_for_human_review', detail
    assert detail['configuration'] == json.loads(before)
    started = next(event for event in detail['events'] if event['stage'] == 'started')
    config = json.loads(started['payload'])['bindings']
    assert config['planner']['adapter'] == 'claude_code'
    assert config['implementer']['model'] == 'frozen-implementer'
    assert config['planner_fallback']['model'] == 'frozen-fallback'
    assert config['agent_timeout'] == 83
    with connection() as conn:
        assert conn.execute('SELECT config FROM managed_runs WHERE run_id=?', (run_id,)).fetchone()['config'] == before


def test_browser_cannot_override_saved_bindings(setup):
    client, project, request, _ = setup
    payload = dict(body(project), bindings={'reviewer': {'adapter': 'fake_review'}})
    assert client.post(url(project, request), json=payload).status_code == 422


def test_idempotent_retry_returns_original_run_after_agent_config_drift(setup, monkeypatch):
    client, project, request, _ = setup
    payload = body(project)
    original = client.post(url(project, request), json=payload).json()
    monkeypatch.setenv('ORCH_PLANNER', 'unsupported')
    monkeypatch.setenv('AGENT_TIMEOUT', 'invalid')
    response = client.post(url(project, request), json=payload)
    assert response.status_code == 202
    assert response.json()['run_id'] == original['run_id']


def test_environment_allowlist_snapshot_is_canonical_and_never_stores_values(setup, monkeypatch):
    client, project, request, _ = setup
    config, old_digest = manager.configuration(project)
    assert 'environment_allowlist' not in config
    monkeypatch.setenv('TEST_FIXTURE_DIR', 'sensitive-value-not-for-the-database')
    monkeypatch.setenv('ORCH_ENV_ALLOWLIST', '{"tests":["TEST_FIXTURE_DIR","TEST_FIXTURE_DIR"]}')
    config, digest = manager.configuration(project)
    assert config['environment_allowlist'] == {'tests': ['TEST_FIXTURE_DIR']}
    assert 'sensitive-value-not-for-the-database' not in json.dumps(config)
    assert digest != old_digest
    monkeypatch.setenv('ORCH_ENV_ALLOWLIST', '{ "tests": ["TEST_FIXTURE_DIR"] }')
    assert manager.configuration(project) == (config, digest)
    response = client.get(f"/projects/{project['id']}/execution-config").json()
    assert response['configuration']['environment_allowlist'] == config['environment_allowlist']
    payload = body(project)
    monkeypatch.setenv('ORCH_ENV_ALLOWLIST', '{"tests":["ANOTHER_FIXTURE_DIR"]}')
    assert client.post(url(project, request), json=payload).status_code == 409


def test_invalid_environment_allowlist_refuses_submission_without_echoing_input(setup, monkeypatch):
    client, project, request, _ = setup
    payload = body(project)
    monkeypatch.setenv('ORCH_ENV_ALLOWLIST', 'invalid-private-policy-value')
    response = client.post(url(project, request), json=payload)
    assert response.status_code == 422
    assert 'invalid-private-policy-value' not in response.text
    with connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM managed_runs').fetchone()[0] == 0


def test_production_worker_environment_and_frozen_policy_reach_real_mocked_workflow(setup, monkeypatch, tmp_path):
    client, project, request, worker = setup
    monkeypatch.setenv('ORCH_ENV_ALLOWLIST', '{"tests":["TEST_FIXTURE_DIR"]}')
    monkeypatch.setenv('TEST_FIXTURE_DIR', '/tmp/authorized-test-fixture')
    monkeypatch.setenv('SENTINEL_SECRET', 'fake-worker-secret')
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-worker-api-key')
    run_id = client.post(url(project, request), json=body(project)).json()['run_id']
    real_python = sys.executable
    fixture = str(Path(__file__).parent / 'fixtures/environment_workflow.py')
    shim = tmp_path / 'mock-workflow-python'
    shim.write_text(f'#!{real_python}\nimport os,sys\nos.execv({real_python!r}, [{real_python!r}, {fixture!r}, sys.argv[-1]])\n')
    shim.chmod(0o755)
    monkeypatch.setenv('ORCH_ENV_ALLOWLIST', '{"tests":["WRONG_DIR"]}')
    # Keep production Worker.spawn/registration/cleanup, replacing only the child executable.
    monkeypatch.setattr('orchestrator.worker.sys.executable', str(shim))
    assert worker.run_once()
    detail = client.get('/runs/' + run_id).json()
    assert detail['status'] == 'ready_for_human_review', detail
    assert detail['tests_passed'] is True
    assert detail['configuration']['environment_allowlist'] == {'tests': ['TEST_FIXTURE_DIR']}
    with connection() as conn:
        stored = ''.join(row[0] for row in conn.execute('SELECT payload FROM events'))
        stored += ''.join(row[0] for row in conn.execute('SELECT config FROM managed_runs'))
    for sentinel in ('fake-worker-secret', 'fake-worker-api-key', '/tmp/authorized-test-fixture'):
        assert sentinel not in stored
