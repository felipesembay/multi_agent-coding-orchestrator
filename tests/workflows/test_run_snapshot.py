import json
import os
from pathlib import Path
import shlex
import sys

import pytest

from orchestrator import core, execution_manager as manager, execution_runner, projects
from orchestrator.project_store import connection
from orchestrator.providers.base import InvocationResult
from orchestrator.worker import Worker
from orchestrator.workflows.store import append_version


@pytest.fixture
def managed_case(snapshot_case, tmp_path, monkeypatch):
    selection, registry, definition = snapshot_case
    root = tmp_path / 'projects'
    root.mkdir()
    monkeypatch.setenv('ORCH_ALLOWED_ROOTS', str(root))
    command = [sys.executable, '-c', "from pathlib import Path; assert Path('output.txt').read_text() == 'done'"]
    monkeypatch.setenv('ORCH_TEST_COMMAND', shlex.join(command))
    monkeypatch.setenv('ORCH_ALLOWED_TEST_COMMANDS', json.dumps([command]))
    monkeypatch.delenv('ORCH_WORKTREES', raising=False)
    monkeypatch.delenv('ORCH_ENV_ALLOWLIST', raising=False)
    preview = projects.preview(projects.ProjectInput(name='Snapshot test', repo_path=str(root / 'repo'), mode='create'))
    project = projects.create(projects.ProjectConfirmation(preview_token=preview['preview_token'], confirmed=True))
    request = projects.submit_request(project['id'], projects.RequestInput(title='Task', content='Original scope'))
    worker = Worker()
    worker.heartbeat()
    seen = []
    get = registry.get
    def runtime(adapter):
        provider = get(adapter)
        def invoke(request):
            seen.append(request)
            if request.role == 'planner':
                return InvocationResult(text=json.dumps({'tasks': [{'id': 'T1', 'title': 'Write output',
                    'instructions': 'Write done', 'acceptance': ['output file exists']}]}))
            if request.role == 'implementer':
                Path(request.cwd, 'output.txt').write_text('done')
                return InvocationResult(text='Updated output.txt')
            return InvocationResult(text='{"approved":true,"findings":[]}')
        provider.invoke = invoke
        return provider
    registry.get = runtime
    return selection, registry, definition, project, request, worker, seen


def queue(case, *, key='snapshot-idempotency-0001'):
    selection, registry, _, project, request, _, _ = case
    config, digest = manager.configuration(project, workflow=selection, provider_registry=registry)
    data = manager.StartInput(confirmed=True, configuration_digest=digest, idempotency_key=key)
    response = manager.submit(project['id'], request['id'], data, workflow=selection, provider_registry=registry)
    return response['run_id'], config, data


def dispatch(case, run_id, monkeypatch):
    _, registry, _, _, _, worker, _ = case
    worker.claim()
    row = manager.get_managed(run_id)
    monkeypatch.setenv('ORCH_DISPATCH_TOKEN', row['dispatch_token'])
    monkeypatch.setenv('ORCH_WORKER_ID', worker.id)
    with connection() as conn:
        conn.execute('UPDATE managed_runs SET pid=? WHERE run_id=?', (os.getpid(), run_id))
        conn.commit()
    return execution_runner.run(run_id, provider_registry=registry)


def test_run_records_snapshot_and_dispatch_ignores_later_changes(managed_case, monkeypatch):
    selection, registry, definition, project, request, _, seen = managed_case
    run_id, config, _ = queue(managed_case)
    assert seen == []  # Preflight and HTTP-equivalent submission never execute agents.
    row = manager.get_managed(run_id)
    assert row['workflow_version_id'] == selection.workflow_version_id
    assert json.loads(row['bindings']) == config['workflow']['bindings']
    assert row['workflow_digest']
    new_version = append_version('wf', {**definition, 'name': 'Changed preset'})
    selection.workflow_version_id = new_version
    selection.bindings['impl'].model = 'changed-after-queue'
    with connection() as conn:
        conn.execute("UPDATE provider_configs SET adapter='missing',enabled=0 WHERE id='pc'")
        conn.execute("UPDATE workflow_definitions SET archived_at=CURRENT_TIMESTAMP WHERE id='wf'")
        conn.execute("UPDATE project_requests SET content='Changed scope' WHERE id=?", (request['id'],))
        conn.commit()
    monkeypatch.setenv('ORCH_PLANNER', 'invalid')
    monkeypatch.setenv('ORCH_IMPLEMENTER', 'invalid')
    assert dispatch(managed_case, run_id, monkeypatch) == 0
    after = manager.get_managed(run_id)
    assert json.loads(after['config']) == config
    assert json.loads(after['result'])['status'] == 'ready_for_human_review'
    assert [r.model for r in seen] == ['plan-model', 'impl-model', 'review-model']
    assert 'Original scope' in seen[0].prompt
    assert 'Changed scope' not in seen[0].prompt
    assert after['workflow_digest'] == row['workflow_digest']


def test_idempotent_retry_returns_original_without_resolving_drift(managed_case):
    selection, registry, _, project, request, _, _ = managed_case
    run_id, _, data = queue(managed_case)
    selection.workflow_version_id = 'missing'
    retried = manager.submit(project['id'], request['id'], data, workflow=selection, provider_registry=registry)
    assert retried['run_id'] == run_id


def test_binding_change_after_preflight_requires_confirmation(managed_case):
    selection, registry, _, project, request, _, _ = managed_case
    _, digest = manager.configuration(project, workflow=selection, provider_registry=registry)
    selection.bindings['impl'].model = 'changed'
    with pytest.raises(projects.ProjectError) as caught:
        manager.submit(project['id'], request['id'], manager.StartInput(
            confirmed=True, configuration_digest=digest, idempotency_key='stale-snapshot-0001'),
            workflow=selection, provider_registry=registry)
    assert caught.value.status == 409


def test_provider_race_inside_reservation_fails_closed(managed_case, monkeypatch):
    selection, registry, _, project, request, _, _ = managed_case
    _, digest = manager.configuration(project, workflow=selection, provider_registry=registry)
    validate = manager.validate_repository
    def drift(project):
        identity = validate(project)
        with connection() as conn:
            conn.execute("UPDATE provider_configs SET enabled=0 WHERE id='pc'")
            conn.commit()
        return identity
    monkeypatch.setattr(manager, 'validate_repository', drift)
    with pytest.raises(projects.ProjectError) as caught:
        manager.submit(project['id'], request['id'], manager.StartInput(
            confirmed=True, configuration_digest=digest, idempotency_key='racing-snapshot-0001'),
            workflow=selection, provider_registry=registry)
    assert caught.value.status == 409
    with connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM managed_runs').fetchone()[0] == 0


@pytest.mark.parametrize('target', ['column', 'config'])
def test_tampered_snapshot_never_creates_worktree_or_calls_agent(managed_case, monkeypatch, target):
    _, _, _, _, _, _, seen = managed_case
    run_id, config, _ = queue(managed_case)
    with connection() as conn:
        if target == 'column':
            conn.execute('UPDATE managed_runs SET workflow_digest=? WHERE run_id=?', ('0' * 64, run_id))
        else:
            config['workflow']['bindings']['impl']['model'] = 'tampered'
            conn.execute('UPDATE managed_runs SET config=? WHERE run_id=?', (json.dumps(config), run_id))
        conn.commit()
    monkeypatch.setattr(core, 'prepare', lambda *args: pytest.fail('No worktree before integrity check'))
    assert dispatch(managed_case, run_id, monkeypatch) == 1
    assert seen == []
    assert json.loads(manager.get_managed(run_id)['result'])['status'] == 'failed'


def test_legacy_configuration_still_has_original_shape(managed_case, monkeypatch):
    _, _, _, project, _, _, _ = managed_case
    monkeypatch.setenv('ORCH_PLANNER', 'claude')
    monkeypatch.setenv('ORCH_IMPLEMENTER', 'claude')
    config, _ = manager.configuration(project)
    assert 'workflow' not in config
    assert 'bindings' not in config


def test_failed_tests_override_positive_agent_review(managed_case, monkeypatch):
    _, _, _, _, _, _, seen = managed_case
    run_id, _, _ = queue(managed_case)
    command = core.run_command
    def fail_tests(argv, *args, **kwargs):
        if argv[0] == sys.executable:
            raise RuntimeError('Synthetic test failure')
        return command(argv, *args, **kwargs)
    monkeypatch.setattr(core, 'run_command', fail_tests)
    assert dispatch(managed_case, run_id, monkeypatch) == 0
    assert json.loads(manager.get_managed(run_id)['result'])['status'] == 'blocked'
    assert len([r for r in seen if r.role == 'implementer']) == 3


def test_agent_failure_payload_is_not_stored_in_errors(managed_case, monkeypatch):
    _, registry, _, _, _, _, _ = managed_case
    run_id, _, _ = queue(managed_case)
    get = registry.get
    def failing(adapter):
        runtime = get(adapter)
        def invoke(request):
            raise RuntimeError('sensitive-runtime-detail')
        runtime.invoke = invoke
        return runtime
    registry.get = failing
    assert dispatch(managed_case, run_id, monkeypatch) == 1
    with core.db(core.db_path()) as conn:
        payloads = conn.execute('SELECT payload FROM events WHERE run_id=?', (run_id,)).fetchall()
    assert 'sensitive-runtime-detail' not in str(payloads)
    assert 'sensitive-runtime-detail' not in manager.get_managed(run_id)['error']


def test_manifest_verification_revoked_after_queue_fails_before_worktree(managed_case, monkeypatch):
    _, registry, _, _, _, _, seen = managed_case
    run_id, _, _ = queue(managed_case)
    registry.get('fake').manifest.verified = False
    monkeypatch.setattr(core, 'prepare', lambda *args: pytest.fail('No worktree after capability revocation'))
    assert dispatch(managed_case, run_id, monkeypatch) == 1
    assert seen == []
