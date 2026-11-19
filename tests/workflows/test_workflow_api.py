import pytest
from fastapi.testclient import TestClient

from orchestrator.api import app
from orchestrator.providers.registry import get_provider_registry
from orchestrator.project_store import connection


@pytest.fixture
def workflow_client(managed_case):
    _, registry, _, _, _, _, _ = managed_case
    app.dependency_overrides[get_provider_registry] = lambda: registry
    try:
        with TestClient(app, base_url='http://127.0.0.1:8765', client=('127.0.0.1', 50000)) as client:
            token = client.get('/session').json()['csrf_token']
            client.headers.update({'Origin': 'http://127.0.0.1:5173', 'X-Orchestrator-CSRF': token})
            yield client, managed_case
    finally:
        app.dependency_overrides.pop(get_provider_registry, None)


def test_create_list_and_append_versions(workflow_client):
    client, case = workflow_client
    definition = case[2]
    response = client.post('/workflows', json={'definition': definition, 'description': 'User workflow'})
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved['read_only'] is False
    assert any(row['id'] == saved['id'] for row in client.get('/workflows').json())
    changed = {**definition, 'name': 'Version two'}
    second = client.post(f"/workflows/{saved['id']}/versions", json={'definition': changed})
    assert second.status_code == 201, second.text
    versions = client.get(f"/workflows/{saved['id']}/versions").json()
    assert [row['version'] for row in versions] == [1, 2]
    assert versions[0]['definition']['name'] == definition['name']
    assert versions[1]['definition']['name'] == 'Version two'


def test_preflight_and_start_use_selected_snapshot_without_agents(workflow_client):
    client, case = workflow_client
    selection, _, _, project, task, _, seen = case
    body = {'workflow': selection.model_dump(mode='json')}
    response = client.post(f"/projects/{project['id']}/execution-config", json=body)
    assert response.status_code == 200, response.text
    assert response.json()['ready'] is True
    start = client.post(f"/projects/{project['id']}/requests/{task['id']}/runs", json={
        **body, 'confirmed': True, 'idempotency_key': 'api-selected-workflow-0001',
        'configuration_digest': response.json()['configuration_digest'],
    })
    assert start.status_code == 202, start.text
    assert seen == []
    with connection() as conn:
        row = conn.execute('SELECT * FROM managed_runs WHERE run_id=?', (start.json()['run_id'],)).fetchone()
        assert row['workflow_version_id'] == selection.workflow_version_id
        assert row['workflow_digest']


def test_validation_reports_fields_without_echoing_inputs(workflow_client):
    client, case = workflow_client
    selection, _, definition, *_ = case
    valid = client.post('/workflows/validate', json={'definition': definition, 'bindings': selection.model_dump(mode='json')['bindings']})
    assert valid.status_code == 200, valid.text
    assert valid.json()['valid'] is True
    definition['steps'][1]['max_attempts'] = 0
    invalid = client.post('/workflows/validate', json={'definition': definition, 'bindings': {}})
    assert invalid.status_code == 422
    assert any('max_attempts' in item['loc'] for item in invalid.json()['detail'])
    assert all('input' not in item for item in invalid.json()['detail'])


def test_presets_are_read_only_and_openrouter_stays_disabled(workflow_client):
    client, case = workflow_client
    presets = {p['id']: p for p in client.get('/workflow-presets').json()}
    assert presets['default-v2']['default_for_ui'] is True
    assert presets['legacy-v1']['default_for_cli'] is True
    assert presets['openrouter-plan']['available'] is False
    assert presets['openrouter-plan']['blocked_by'] == []
    with connection() as conn:
        conn.execute("UPDATE workflow_definitions SET is_preset=1 WHERE id='wf'")
        conn.commit()
    response = client.post('/workflows/wf/versions', json={'definition': case[2]})
    assert response.status_code == 403
    assert client.post('/workflows', json={'preset_id': 'openrouter-plan'}).status_code == 201


def test_local_provider_config_only_uses_registered_adapter_no_secret_fields(workflow_client):
    client, _ = workflow_client
    response = client.post('/provider-configs', json={'adapter': 'fake', 'display_name': 'My runtime'})
    assert response.status_code == 201, response.text
    rows = client.get('/provider-configs').json()
    assert any(r['id'] == response.json()['id'] for r in rows)
    assert all('settings' not in r and 'credential_ref' not in r for r in rows)
    rejected = client.post('/provider-configs', json={'adapter': 'fake', 'api_key': 'sensitive-input'})
    assert rejected.status_code == 422
    assert 'sensitive-input' not in rejected.text
    assert client.post('/provider-configs', json={'adapter': 'not-registered', 'display_name': 'Unknown'}).status_code == 422


def test_new_routes_are_globally_authenticated_and_missing_workflow_is_404(workflow_client):
    client, _ = workflow_client
    assert client.get('/workflows/missing/versions').status_code == 404
    for path in ('/workflows', '/workflow-presets', '/provider-configs'):
        assert client.get(path, headers={'Host': 'evil.invalid'}).status_code == 403
        token = client.headers.pop('X-Orchestrator-CSRF')
        assert client.get(path).status_code == 403
        client.headers['X-Orchestrator-CSRF'] = token


def test_clone_legacy_has_user_identity_and_blank_names_are_rejected(workflow_client):
    client, _ = workflow_client
    created = client.post('/workflows', json={'preset_id': 'legacy-v1', 'name': 'legacy-v1'})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body['read_only'] is False
    assert body['id'] != 'legacy-v1'
    assert [s['type'] for s in body['latest_version']['definition']['steps']] == ['plan', 'implement', 'test', 'review']
    assert client.post('/workflows', json={'preset_id': 'default-v2', 'name': '   '}).status_code == 422


def test_model_provider_cannot_edit_and_errors_identify_binding(workflow_client):
    client, case = workflow_client
    selection, registry, definition, *_ = case
    registry.get('fake').manifest.kind = 'model_provider'
    with connection() as conn:
        conn.execute("UPDATE provider_configs SET kind='model_provider' WHERE id='pc'")
        conn.commit()
    response = client.post('/workflows/validate', json={
        'definition': definition, 'bindings': selection.model_dump(mode='json')['bindings']})
    assert response.status_code == 422
    assert any('impl' in error['loc'] for error in response.json()['detail'])


def test_valid_but_unintegrated_feature_is_not_executable(workflow_client):
    client, case = workflow_client
    selection, _, definition, *_ = case
    definition['approval']['human_gate_after_plan'] = True
    response = client.post('/workflows/validate', json={
        'definition': definition, 'bindings': selection.model_dump(mode='json')['bindings']})
    assert response.status_code == 200
    assert response.json()['valid'] is True
    assert response.json()['executable'] is False


def test_legacy_get_preflight_contract_and_provider_config_rejection(workflow_client):
    client, case = workflow_client
    project = case[3]
    response = client.get(f"/projects/{project['id']}/execution-config")
    assert response.status_code == 200
    assert 'workflow' not in response.json()['configuration']
    with connection() as conn:
        before = conn.execute('SELECT COUNT(*) FROM provider_configs').fetchone()[0]
    rejected = client.post('/provider-configs', json={'adapter': 'fake', 'display_name': 'Bad',
        'settings': {'api_key': 'do-not-echo'}, 'enabled_entry_points': ['bad']})
    assert rejected.status_code == 422
    assert 'do-not-echo' not in rejected.text
    with connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM provider_configs').fetchone()[0] == before


def test_known_model_default_is_frozen_before_worker_environment_drift(workflow_client, monkeypatch):
    from orchestrator.workflows.snapshot import load_snapshot
    from orchestrator.providers.base import InvocationRequest
    from orchestrator.providers.runtimes.antigravity import AntigravityRuntime
    import json

    _, case = workflow_client
    selection, registry, *_ = case
    registry.get('fake').manifest.adapter = 'antigravity'
    with connection() as conn:
        conn.execute("UPDATE provider_configs SET adapter='antigravity' WHERE id='pc'")
        conn.commit()
    selection.bindings['plan'].model = None
    monkeypatch.setenv('ORCH_ANTIGRAVITY_MODEL', 'confirmed-default')
    frozen = load_snapshot(selection, registry=registry)
    assert frozen.bindings['plan'].model == 'confirmed-default'
    assert selection.bindings['plan'].model is None
    monkeypatch.setenv('ORCH_ANTIGRAVITY_MODEL', 'worker-drift')
    argv = []
    def runner(command, *args, **kwargs):
        argv.extend(command)
        return json.dumps({'status': 'SUCCESS', 'response': 'mocked'})
    result = AntigravityRuntime(runner).invoke(InvocationRequest(
        role='planner', prompt='fake', cwd='/tmp', permission='read_only',
        model=frozen.bindings['plan'].model))
    assert result.text == 'mocked'
    assert argv[argv.index('--model') + 1] == 'confirmed-default'


def test_editor_validates_definition_without_binding_or_agent_lookups(workflow_client):
    client, case = workflow_client
    _, registry, definition, *_ = case
    registry.get = lambda adapter: pytest.fail('Structural editor validation must not resolve providers')
    response = client.post('/workflows/validate', json={'definition': definition})
    assert response.status_code == 200, response.text
    assert response.json() == {'valid': True, 'executable': None, 'errors': [], 'validation_scope': 'definition'}
    definition['steps'][1]['max_attempts'] = 0
    assert client.post('/workflows/validate', json={'definition': definition}).status_code == 422


def test_new_version_renames_metadata_without_mutating_previous_version(workflow_client):
    client, case = workflow_client
    initial = client.get('/workflows/wf/versions').json()[0]
    changed = {**case[2], 'name': 'Edited workflow name'}
    assert client.post('/workflows/wf/versions', json={'definition': changed}).status_code == 201
    saved = next(row for row in client.get('/workflows').json() if row['id'] == 'wf')
    assert saved['name'] == 'Edited workflow name'
    assert client.get('/workflows/wf/versions').json()[0] == initial
