"""No CLI invocations: normalized failures and real queue/SQLite with fake runtimes."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from orchestrator import core, execution_manager as manager, execution_runner
from orchestrator.project_store import connection
from orchestrator.providers.base import InvocationResult, UsageReport
from orchestrator.providers.errors import InvocationFailure
from orchestrator.workflows.compiler import compile_workflow
from orchestrator.workflows.nodes import WorkflowLimitError
from orchestrator.workflows.schema import FallbackBinding
from orchestrator.workflows.snapshot import load_snapshot, WorkflowSnapshotError
from orchestrator.workflows.store import append_version


def fallback_case(case, conditions=('quota_exhausted',), step='plan'):
    args, calls, events = case
    args['bindings'][step]['fallbacks'] = [
        {'provider_config_id': 'pc', 'model': 'backup', 'on': list(conditions),
         'permission': args['bindings'][step].get('permission', 'read_only')},
    ]
    return args, calls, events


@pytest.fixture
def case(definition):
    from orchestrator.providers.base import CapabilityManifest
    manifest = CapabilityManifest(adapter='fake', kind='agent_runtime',
        capabilities=['text', 'planning', 'code_edit', 'review', 'structured_output'],
        permission_modes=['read_only', 'workspace_write'], auth_modes=['none'],
        billing_mode='local', usage_source='none', verified=True)
    calls, events = [], []
    def execute(context):
        calls.append(context)
        return {'plan': {'tasks': [{'id': 'T1'}]}, 'implement': {'output': 'done'},
                'test': {'passed': True}, 'review': {'approved': True, 'findings': []}}[context.step.type]
    return dict(definition=definition, bindings={
        'plan': {'provider_config_id': 'pc'},
        'impl': {'provider_config_id': 'pc', 'permission': 'workspace_write'},
        'review': {'provider_config_id': 'pc'}}, provider_configs={'pc': 'fake'},
        registry=SimpleNamespace(get=lambda _: SimpleNamespace(manifest=manifest)),
        executors={kind: execute for kind in ('plan', 'implement', 'test', 'review')},
        event_sink=lambda state, stage, payload: events.append((stage, payload))), calls, events


@pytest.mark.parametrize('code', ['quota_exhausted', 'rate_limited', 'unavailable'])
def test_matching_safe_failure_uses_frozen_fallback(case, code):
    args, calls, events = fallback_case(case, [code])
    execute = args['executors']['plan']
    def fail_primary(context):
        if context.binding.model != 'backup':
            calls.append(context)
            raise InvocationFailure(code, safe_to_retry=True)
        return execute(context)
    args['executors']['plan'] = fail_primary
    result = compile_workflow(**args).invoke({})
    assert result['status'] == 'ready_for_human_review'
    assert result['workflow_steps'] == 5
    assert calls[1].binding.model == 'backup'
    assert calls[1].retry_of == calls[0].call_id
    assert calls[1].call_id != calls[0].call_id
    event = next(payload for stage, payload in events if stage == 'agent_fallback')
    assert event['step_id'] == 'plan' and event['reason'] == code
    assert event['retry_of'] == calls[0].call_id


@pytest.mark.parametrize('failure', [
    InvocationFailure('quota_exhausted'), InvocationFailure('auth_failed', safe_to_retry=True),
    InvocationFailure('timeout', safe_to_retry=True), RuntimeError('quota exceeded secret'),
    InvocationFailure('rate_limited', safe_to_retry=True),
])
def test_unsafe_unmatched_or_ambiguous_errors_never_retry(case, failure):
    args, calls, events = fallback_case(case)
    def fail(context):
        calls.append(context)
        raise failure
    args['executors']['plan'] = fail
    with pytest.raises(Exception):
        compile_workflow(**args).invoke({})
    assert len(calls) == 1
    assert not any(stage == 'agent_fallback' for stage, _ in events)


def test_fallbacks_are_ordered_skip_nonmatching_and_never_cycle(case):
    args, calls, events = fallback_case(case)
    args['bindings']['plan']['fallbacks'] = [
        {'provider_config_id': 'pc', 'model': model, 'on': [code]}
        for model, code in [('skip', 'rate_limited'), ('first', 'quota_exhausted'), ('last', 'unavailable')]]
    execute = args['executors']['plan']
    def invoke(context):
        if context.binding.model != 'last':
            calls.append(context)
            raise InvocationFailure('quota_exhausted' if context.binding.model is None else 'unavailable', safe_to_retry=True)
        return execute(context)
    args['executors']['plan'] = invoke
    compile_workflow(**args).invoke({})
    assert [c.binding.model for c in calls if c.step.id == 'plan'] == [None, 'first', 'last']


@pytest.mark.parametrize('limit', ['duration', 'steps', 'attempts'])
def test_retry_obeys_global_deadline_steps_and_implementation_attempts(case, limit):
    step = 'impl' if limit == 'attempts' else 'plan'
    args, calls, events = fallback_case(case, step=step)
    now = [0]
    args['clock'] = lambda: now[0]
    if limit == 'steps': args['definition']['limits']['max_total_steps'] = 1
    if limit == 'attempts': args['definition']['steps'][1]['max_attempts'] = 1
    def fail(context):
        calls.append(context)
        if limit == 'duration': now[0] = 15000
        raise InvocationFailure('quota_exhausted', safe_to_retry=True)
    args['executors']['implement' if limit == 'attempts' else 'plan'] = fail
    with pytest.raises(WorkflowLimitError): compile_workflow(**args).invoke({})
    assert len([c for c in calls if c.step.id == step]) == 1


def test_exhausted_chain_stops_and_records_failed_stage(case):
    args, calls, events = fallback_case(case)
    def fail(context):
        calls.append(context)
        raise InvocationFailure('quota_exhausted', safe_to_retry=True)
    args['executors']['plan'] = fail
    with pytest.raises(InvocationFailure): compile_workflow(**args).invoke({})
    assert len(calls) == 2
    assert events[-1] == ('stage_finished', {'step_id': 'plan', 'stage': 'plan', 'status': 'failed'})


def test_implementation_fallbacks_consume_attempts_and_keep_permissions(case):
    args, calls, events = fallback_case(case, step='impl')
    execute = args['executors']['implement']
    def invoke(context):
        if context.binding.model != 'backup':
            calls.append(context)
            raise InvocationFailure('quota_exhausted', safe_to_retry=True)
        return execute(context)
    args['executors']['implement'] = invoke
    result = compile_workflow(**args).invoke({})
    assert result['workflow_attempts']['impl:0'] == 2
    assert [c.binding.permission for c in calls if c.step.id == 'impl'] == ['workspace_write', 'workspace_write']


def test_deadline_includes_fallback_event_and_prevents_next_invocation(case):
    args, calls, events = fallback_case(case)
    now = [0]
    args['clock'] = lambda: now[0]
    def emit(state, stage, payload):
        events.append((stage, payload))
        if stage == 'agent_fallback': now[0] = 15000
    def fail(context):
        calls.append(context)
        raise InvocationFailure('quota_exhausted', safe_to_retry=True)
    args['event_sink'], args['executors']['plan'] = emit, fail
    with pytest.raises(WorkflowLimitError): compile_workflow(**args).invoke({})
    assert len(calls) == 1


def test_document_fallback_cannot_escalate_readonly_permission(case):
    args, _, _ = case
    args['definition']['steps'].append({'id': 'doc', 'type': 'document'})
    args['bindings']['doc'] = {'provider_config_id': 'pc', 'fallbacks': [
        {'provider_config_id': 'pc', 'on': ['unavailable'], 'permission': 'workspace_write'}]}
    args['executors']['document'] = lambda context: {'text': 'docs'}
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match='increase primary permission'): compile_workflow(**args)


@pytest.mark.parametrize('mode', ['success', 'journal_failure', 'unsafe', 'error_result'])
def test_queue_dispatch_records_each_usage_and_ignores_fallback_config_drift(managed_case, monkeypatch, mode):
    selection, registry, _, project, request, worker, seen = managed_case
    original_get = registry.get
    manifest = original_get('fake').manifest.model_copy(update={'adapter': 'backup'})
    backup_calls = []
    def backup(req):
        backup_calls.append(req)
        return InvocationResult(
            text=json.dumps({'tasks': [{'id': 'T1', 'title': 'Write', 'instructions': 'Write', 'acceptance': ['done']}]}),
            usage=UsageReport(input_tokens=7, output_tokens=3, source='provider_reported', raw={'secret': 'never retain'}))
    def get(adapter):
        if adapter == 'fake':
            provider = original_get(adapter)
            invoke = provider.invoke
            def primary(req):
                if req.role == 'planner':
                    if mode == 'error_result': return InvocationResult(text='must not parse', error_code='quota_exhausted')
                    raise InvocationFailure('quota_exhausted', safe_to_retry=mode != 'unsafe')
                return invoke(req)
            provider.invoke = primary
            return provider
        assert adapter == 'backup'
        return SimpleNamespace(manifest=manifest, invoke=backup)
    registry.get = get
    with connection() as conn:
        conn.execute("INSERT INTO provider_configs(id,kind,adapter,display_name,enabled) VALUES('backup-config','agent_runtime','backup','Backup',1)")
        conn.commit()
    selection.bindings['plan'].fallbacks = [FallbackBinding(provider_config_id='backup-config', model='frozen-backup', on=['quota_exhausted'])]
    config, digest = manager.configuration(project, workflow=selection, provider_registry=registry)
    response = manager.submit(project['id'], request['id'], manager.StartInput(confirmed=True,
        configuration_digest=digest, idempotency_key='fallback-snapshot-0001'), workflow=selection, provider_registry=registry)
    run_id = response['run_id']
    with connection() as conn:
        conn.execute("UPDATE provider_configs SET adapter='missing',enabled=0 WHERE id='backup-config'")
        conn.commit()
    worker.claim()
    row = manager.get_managed(run_id)
    monkeypatch.setenv('ORCH_DISPATCH_TOKEN', row['dispatch_token'])
    monkeypatch.setenv('ORCH_WORKER_ID', worker.id)
    with connection() as conn:
        conn.execute('UPDATE managed_runs SET pid=? WHERE run_id=?', (os.getpid(), run_id))
        conn.commit()
    if mode == 'journal_failure':
        event = core.event
        def broken(state, stage, payload):
            if stage == 'usage_record': raise RuntimeError('journal unavailable')
            event(state, stage, payload)
        monkeypatch.setattr(core, 'event', broken)
    status = execution_runner.run(run_id, provider_registry=registry)
    if mode != 'success':
        assert status == 1 and backup_calls == []
        return
    assert status == 0 and len(backup_calls) == 1
    with core.db(core.db_path()) as conn:
        events = [(s, json.loads(p)) for s, p in conn.execute('SELECT stage,payload FROM events WHERE run_id=?', (run_id,))]
    records = [p for s, p in events if s == 'usage_record' and p['step_id'] == 'plan']
    assert len(records) == 2
    assert records[0]['token_source'] == 'unavailable' and records[0]['input_tokens'] is None
    assert records[1]['input_tokens'] == 7 and records[1]['retry_of'] == records[0]['call_id']
    assert records[1]['model'] == 'frozen-backup'
    assert records[1]['billing_mode'] == 'local'
    assert 'never retain' not in json.dumps(events)
    assert len([p for s, p in events if s == 'agent_call' and p['step_id'] == 'plan']) == 2
    assert any(s == 'agent_fallback' and p['step_id'] == 'plan' for s, p in events)


@pytest.mark.parametrize('feature', ['disabled', 'parameters', 'unsupported_model', 'kind', 'permission'])
def test_every_fallback_is_checked_before_queue(snapshot_case, feature):
    selection, registry, _ = snapshot_case
    selection.bindings['plan'].fallbacks = [FallbackBinding(provider_config_id='pc', on=['unavailable'])]
    if feature == 'disabled':
        selection.bindings['plan'].fallbacks[0].provider_config_id = 'missing'
    elif feature == 'parameters': selection.bindings['plan'].fallbacks[0].parameters = {'secret': 'x'}
    elif feature == 'unsupported_model':
        get = registry.get
        registry.get = lambda adapter: SimpleNamespace(manifest=registry_manifest('codex_cli')) if adapter == 'codex_cli' else get(adapter)
        with connection() as conn:
            conn.execute("INSERT INTO provider_configs(id,kind,adapter,display_name,enabled) VALUES('backup-config','agent_runtime','codex_cli','Backup',1)"); conn.commit()
        selection.bindings['plan'].fallbacks[0].provider_config_id = 'backup-config'
        selection.bindings['plan'].fallbacks[0].model = 'unsupported'
    elif feature == 'kind':
        with connection() as conn:
            conn.execute("UPDATE provider_configs SET kind='model_provider' WHERE id='pc'"); conn.commit()
    else: selection.bindings['plan'].fallbacks[0].permission = 'workspace_write'
    with pytest.raises(WorkflowSnapshotError): load_snapshot(selection, registry=registry)


def test_antigravity_fallback_default_is_frozen_and_input_is_not_mutated(snapshot_case, monkeypatch):
    selection, registry, _ = snapshot_case
    get = registry.get
    registry.get = lambda adapter: SimpleNamespace(manifest=registry_manifest('antigravity')) if adapter == 'antigravity' else get(adapter)
    with connection() as conn:
        conn.execute("INSERT INTO provider_configs(id,kind,adapter,display_name,enabled) VALUES('agy-backup','agent_runtime','antigravity','AGY',1)"); conn.commit()
    selection.bindings['plan'].fallbacks = [FallbackBinding(provider_config_id='agy-backup', on=['unavailable'])]
    monkeypatch.setenv('ORCH_ANTIGRAVITY_MODEL', 'confirmed-default')
    snapshot = load_snapshot(selection, registry=registry)
    monkeypatch.setenv('ORCH_ANTIGRAVITY_MODEL', 'worker-drift')
    assert snapshot.bindings['plan'].fallbacks[0].model == 'confirmed-default'
    assert selection.bindings['plan'].fallbacks[0].model is None
    assert set(snapshot.providers) == {'pc', 'agy-backup'}


def registry_manifest(adapter):
    from orchestrator.providers.base import CapabilityManifest
    return CapabilityManifest(adapter=adapter, kind='agent_runtime', capabilities=['text', 'planning', 'review', 'code_edit', 'structured_output'],
        permission_modes=['read_only', 'workspace_write'], auth_modes=['none'], billing_mode='unknown', usage_source='none', verified=True)


def test_usage_attempts_remain_cumulative_across_review_returns(managed_case, monkeypatch):
    selection, registry, definition, project, request, worker, _ = managed_case
    definition['steps'][1]['max_attempts'] = 6
    selection.workflow_version_id = append_version('wf', definition)
    selection.bindings['impl'].fallbacks = [FallbackBinding(provider_config_id='pc', model='backup',
        permission='workspace_write', on=['quota_exhausted'])]
    original_get, reviews = registry.get, []
    def get(adapter):
        runtime = original_get(adapter)
        invoke = runtime.invoke
        def wrapped(req):
            if req.role == 'implementer':
                if req.model != 'backup': raise InvocationFailure('quota_exhausted', safe_to_retry=True)
                Path(req.cwd, 'output.txt').write_text('done')
                return InvocationResult(text='done')
            if req.role == 'reviewer':
                reviews.append(True)
                return InvocationResult(text=json.dumps({'approved': len(reviews) > 1, 'findings': []}))
            return invoke(req)
        runtime.invoke = wrapped
        return runtime
    registry.get = get
    _, digest = manager.configuration(project, workflow=selection, provider_registry=registry)
    response = manager.submit(project['id'], request['id'], manager.StartInput(confirmed=True,
        configuration_digest=digest, idempotency_key='cumulative-attempt-0001'), workflow=selection, provider_registry=registry)
    run_id = response['run_id']
    worker.claim()
    row = manager.get_managed(run_id)
    monkeypatch.setenv('ORCH_DISPATCH_TOKEN', row['dispatch_token'])
    monkeypatch.setenv('ORCH_WORKER_ID', worker.id)
    with connection() as conn:
        conn.execute('UPDATE managed_runs SET pid=? WHERE run_id=?', (os.getpid(), run_id)); conn.commit()
    assert execution_runner.run(run_id, provider_registry=registry) == 0
    with core.db(core.db_path()) as conn:
        records = [json.loads(row[0]) for row in conn.execute(
            "SELECT payload FROM events WHERE run_id=? AND stage='usage_record' ORDER BY id", (run_id,))]
    attempts = [record for record in records if record['step_id'] == 'impl']
    assert [r['attempt'] for r in attempts] == [1, 2, 3, 4]
    assert [r['chain_attempt'] for r in attempts] == [1, 2, 1, 2]
    assert attempts[2]['retry_of'] is None
