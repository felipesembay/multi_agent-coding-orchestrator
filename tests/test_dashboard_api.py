import json

import pytest
from fastapi.testclient import TestClient

from orchestrator.api import app
from orchestrator.core import db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('ORCH_DB', str(tmp_path / 'events.db'))
    monkeypatch.setenv('PRIVATE_TOKEN', 'do-not-expose')
    with TestClient(app) as client:
        yield client


def record(stage, payload, run='run-one', at='2026-11-05 12:00:00'):
    from orchestrator.core import db_path
    with db(db_path()) as conn:
        conn.execute('INSERT INTO events(run_id,stage,payload,at) VALUES(?,?,?,?)',
                     (run, stage, json.dumps(payload), at))


def test_empty_and_missing(client):
    assert client.get('/health').json() == {'status': 'ok'}
    assert client.get('/runs').json() == []
    assert client.get('/runs?paginated=true').json()['total'] == 0
    assert client.get('/overview').json()['average_duration_seconds'] is None
    assert client.get('/runs/missing').status_code == 404
    assert client.get('/runs/missing/events').json() == []


def test_status_duration_legacy_contract_and_event_order(client):
    record('started', {'repo': '/repo', 'worktree': '/tree'})
    record('plan', {'tasks': [{'id': 'T1'}]})
    record('implementation', {'task': 'T1', 'attempt': 1})
    record('review', {'approved': True, 'test_result': {'passed': True}})
    record('finished', {'status': 'ready_for_human_review'}, at='2026-11-05 12:02:00')
    runs = client.get('/runs').json()
    assert isinstance(runs, list)
    assert runs[0]['last_event'] == '2026-11-05 12:02:00'
    assert runs[0]['status'] == 'ready_for_human_review'
    assert runs[0]['duration_seconds'] == 120
    assert runs[0]['tests_passed'] is True
    detail = client.get('/runs/run-one').json()
    assert detail['task_count'] == 1
    assert [e['stage'] for e in detail['events']] == ['started', 'plan', 'implementation', 'review', 'finished']
    assert isinstance(detail['events'][0]['payload'], str)
    overview = client.get('/overview').json()
    assert overview['counts'] == {'ready_for_human_review': 1}
    assert overview['average_duration_seconds'] == 120


def test_final_payload_and_resume_override_terminal_state(client):
    record('started', {})
    record('blocked', {})
    record('resumed', {})
    assert client.get('/runs/run-one').json()['status'] == 'running'
    assert client.get('/runs/run-one').json()['duration_seconds'] is None
    record('finished', {'status': 'failed'})
    assert client.get('/runs/run-one').json()['status'] == 'failed'
    record('finished', {})
    assert client.get('/runs/run-one').json()['status'] == 'unknown'


def test_malformed_unknown_and_parameter_safety(client):
    from orchestrator.core import db_path
    with db(db_path()) as conn:
        conn.execute("INSERT INTO events(run_id,stage,payload) VALUES(?,?,?)", ('broken', 'finished', '{invalid'))
    record('custom', ['a', 'b'], run='custom')
    assert client.get('/runs/broken').json()['status'] == 'unknown'
    assert client.get('/runs/custom').json()['status'] == 'unknown'
    assert client.get('/runs/custom/events').json()[0]['stage'] == 'custom'
    assert client.get("/runs?search=%27%20OR%201%3D1--").json() == []
    assert client.get('/runs?limit=101').status_code == 422
    assert client.get('/runs?offset=-1').status_code == 422


def test_pagination_filters_and_all_run_metrics(client):
    for i in range(55):
        record('started', {}, run=f'run-{i:02d}')
    page = client.get('/runs?paginated=true&limit=10&offset=10&order=asc').json()
    assert page['total'] == 55
    assert len(page['items']) == 10
    assert page['items'][0]['run_id'] == 'run-10'
    assert client.get('/overview').json()['total'] == 55
    assert len(client.get('/runs').json()) == 50
    assert client.get('/runs?search=run-01&status=running').json()[0]['run_id'] == 'run-01'
    assert client.get('/runs?status=blocked').json() == []


def test_settings_allowlist_and_read_only(client):
    settings = client.get('/settings').json()
    assert 'do-not-expose' not in json.dumps(settings)
    assert 'PRIVATE_TOKEN' not in settings
    assert settings['reviewer'] == 'codex'
    assert client.post('/runs', json={}).status_code == 405


def test_incomplete_and_wrongly_typed_payloads_remain_unknown(client):
    record('started', {'repo': {'bad': 'type'}, 'worktree': 42})
    record('plan', {'tasks': 'not-a-list'})
    record('review', {'test_result': {'passed': 'true'}})
    result = client.get('/runs/run-one').json()
    assert result['repo'] is None
    assert result['worktree'] is None
    assert result['task_count'] is None
    assert result['tests_passed'] is None
    assert result['duration_seconds'] is None
    record('finished', {'status': ['success']})
    assert client.get('/runs/run-one').json()['status'] == 'unknown'
