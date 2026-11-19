import json
import os

import httpx
import pytest

from orchestrator import core, execution_manager as manager, execution_runner
from orchestrator.project_store import connection
from orchestrator.providers.models.openrouter import OpenRouterProvider
from orchestrator.secrets.store import CredentialStore, InMemoryKeyringBackend, bind_provider_credential
from orchestrator.workflows.schema import StepBinding
from orchestrator.workflows.snapshot import WorkflowSnapshotError, load_snapshot


@pytest.fixture
def api_case(managed_case):
    selection, registry, definition, project, request, worker, seen = managed_case
    credentials = CredentialStore(backend=InMemoryKeyringBackend())
    with connection() as conn:
        conn.execute("INSERT INTO provider_configs(id,kind,adapter,display_name,enabled) VALUES('api','model_provider','openrouter','API',1)")
        conn.commit()
    bind_provider_credential('api', 'sentinel-api-key-original', store=credentials)
    calls = []
    def handle(req):
        calls.append(req)
        data = json.loads(req.content)
        assert data['model'] == 'vendor/model'
        assert not any(name in data for name in ('cwd','env','credential_ref'))
        if data['messages'][1]['content'].startswith('Independently review'):
            assert 'done' in data['messages'][-1]['content']  # Includes actual untracked file content.
            payload = {'approved':True, 'findings':[]}
        else:
            payload = {'tasks':[{'id':'T1','title':'Write','instructions':'Write','acceptance':['done']}]}
        return httpx.Response(200, json={'model':'vendor/model', 'choices':[
            {'finish_reason':'stop', 'message':{'content':json.dumps(payload)}}],
            'usage':{'prompt_tokens':8,'completion_tokens':4,'cost':0.001}})
    provider = OpenRouterProvider(credential_store=credentials, transport=httpx.MockTransport(handle))
    get = registry.get
    registry.get = lambda adapter: provider if adapter == 'openrouter' else get(adapter)
    selection.bindings['plan'] = StepBinding(provider_config_id='api', model='vendor/model')
    selection.bindings['review'] = StepBinding(provider_config_id='api', model='vendor/model')
    return managed_case, credentials, calls


def test_model_provider_queue_dispatch_usage_keyring_and_frozen_reference(api_case, monkeypatch):
    case, credentials, calls = api_case
    selection, registry, _, project, request, worker, seen = case
    config, digest = manager.configuration(project, workflow=selection, provider_registry=registry)
    assert calls == []  # No generation in preflight or submit.
    response = manager.submit(project['id'], request['id'], manager.StartInput(confirmed=True,
        configuration_digest=digest, idempotency_key='api-snapshot-0001'), workflow=selection, provider_registry=registry)
    run_id = response['run_id']
    # Keys rotate in keyring; reference/identity remain frozen despite DB drift.
    credentials.set_credential('openrouter','api','sentinel-api-key-rotated')
    with connection() as conn:
        conn.execute("UPDATE provider_configs SET adapter='missing',credential_ref='wrong',enabled=0 WHERE id='api'")
        conn.commit()
    worker.claim()
    row = manager.get_managed(run_id)
    monkeypatch.setenv('ORCH_DISPATCH_TOKEN',row['dispatch_token'])
    monkeypatch.setenv('ORCH_WORKER_ID',worker.id)
    with connection() as conn:
        conn.execute('UPDATE managed_runs SET pid=? WHERE run_id=?',(os.getpid(),run_id)); conn.commit()
    assert execution_runner.run(run_id,provider_registry=registry) == 0
    assert len(calls) == 2
    assert all(call.headers['authorization'] == 'Bearer sentinel-api-key-rotated' for call in calls)
    assert [req.role for req in seen] == ['implementer']
    with connection() as conn:
        usage = conn.execute("SELECT * FROM usage_records WHERE run_id=? AND adapter='openrouter'",(run_id,)).fetchall()
        assert len(usage) == 2
        assert all(row['token_source']=='provider_reported' and row['billing_mode']=='api_metered' for row in usage)
        assert all(row['input_tokens']==8 and row['output_tokens']==4 for row in usage)
        dump = '\n'.join(conn.iterdump())
    assert 'sentinel-api-key-' not in dump
    assert b'sentinel-api-key-' not in open(core.db_path(),'rb').read()
    assert config['workflow']['providers']['api']['credential_ref'] == 'multi-agent-orchestrator:openrouter:api'


@pytest.mark.parametrize('change', ['model','reference','permission','implementation'])
def test_invalid_api_selection_fails_before_generation(api_case,change):
    case, _, calls = api_case
    selection, registry, *_ = case
    if change == 'model': selection.bindings['plan'].model = None
    elif change == 'reference':
        with connection() as conn:
            conn.execute("UPDATE provider_configs SET credential_ref='multi-agent-orchestrator:other:api' WHERE id='api'");conn.commit()
    elif change == 'permission': selection.bindings['plan'].permission='workspace_write'
    else: selection.bindings['impl']=StepBinding(provider_config_id='api',model='vendor/model',permission='workspace_write')
    with pytest.raises(WorkflowSnapshotError): load_snapshot(selection,registry=registry)
    assert calls == []


@pytest.mark.parametrize('failure',['invalid_json','oversized_prompt'])
def test_failed_model_output_preserves_usage_and_closes_ledger(api_case,monkeypatch,failure):
    case, _, calls = api_case
    selection, registry, _, project, request, worker, _ = case
    api = registry.get('openrouter')
    original = api._request
    def altered(*args,**kwargs):
        data = original(*args,**kwargs)
        review = kwargs['body']['messages'][1]['content'].startswith('Independently review')
        if failure == 'invalid_json' and review:
            data['choices'][0]['message']['content'] = '{broken'
        elif failure == 'oversized_prompt' and not review:
            payload = json.loads(data['choices'][0]['message']['content'])
            payload['tasks'][0]['instructions'] = 'x'*100001
            data['choices'][0]['message']['content'] = json.dumps(payload)
        return data
    monkeypatch.setattr(api,'_request',altered)
    _,digest = manager.configuration(project,workflow=selection,provider_registry=registry)
    run_id = manager.submit(project['id'],request['id'],manager.StartInput(confirmed=True,
        configuration_digest=digest,idempotency_key='failed-api-output-0001'),workflow=selection,provider_registry=registry)['run_id']
    worker.claim();row=manager.get_managed(run_id)
    monkeypatch.setenv('ORCH_DISPATCH_TOKEN',row['dispatch_token']);monkeypatch.setenv('ORCH_WORKER_ID',worker.id)
    with connection() as conn:
        conn.execute('UPDATE managed_runs SET pid=? WHERE run_id=?',(os.getpid(),run_id));conn.commit()
    assert execution_runner.run(run_id,provider_registry=registry)==1
    with connection() as conn:
        usage=conn.execute("SELECT * FROM usage_records WHERE run_id=? AND adapter='openrouter'",(run_id,)).fetchall()
        assert len(usage)==(2 if failure=='invalid_json' else 1)
        assert all(row['input_tokens']==8 and row['token_source']=='provider_reported' for row in usage)
        review=conn.execute("SELECT status FROM step_executions WHERE run_id=? AND node='review'",(run_id,)).fetchone()
        assert review['status']=='failed'
    with core.db(core.db_path()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events WHERE run_id=? AND stage='agent_fallback'",(run_id,)).fetchone()[0]==0
