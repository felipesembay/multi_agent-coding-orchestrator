from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from orchestrator.providers.base import CapabilityManifest
from orchestrator.workflows.compiler import compile_workflow
from orchestrator.workflows.nodes import WorkflowLimitError


@pytest.fixture
def case(definition):
    manifest = CapabilityManifest(
        adapter='fake', kind='agent_runtime',
        capabilities=['text', 'planning', 'code_edit', 'review', 'structured_output'],
        permission_modes=['read_only', 'workspace_write'], auth_modes=['none'],
        billing_mode='local', usage_source='none', verified=True,
    )
    class Registry:
        def get(self, adapter):
            assert adapter == 'fake'
            return SimpleNamespace(manifest=manifest)
    calls, events = [], []
    def execute(context):
        calls.append(context)
        return {'plan': {'tasks': [{'id': 'T1'}, {'id': 'T2'}]},
                'implement': {'output': 'done'}, 'test': {'passed': True},
                'review': {'approved': True, 'findings': []},
                'document': {'text': 'docs'}, 'human_gate': {'approved': True}}[context.step.type]
    return dict(
        definition=definition,
        bindings={'plan': {'provider_config_id': 'pc'},
                  'impl': {'provider_config_id': 'pc', 'permission': 'workspace_write'},
                  'review': {'provider_config_id': 'pc'}},
        provider_configs={'pc': 'fake'}, registry=Registry(),
        executors={kind: execute for kind in ('plan', 'implement', 'test', 'review', 'document', 'human_gate')},
        event_sink=lambda state, stage, payload: events.append((stage, payload)),
    ), calls, events


def test_compiler_requires_host_executors(definition):
    with pytest.raises(ValueError, match='executor'):
        compile_workflow(definition, {}, provider_configs={}, registry=None, executors={})


def test_two_tasks_and_events(case):
    args, calls, events = case
    graph = compile_workflow(**args)
    result = graph.invoke({'run_id': 'fake-run', 'scope': 'scope'})
    assert [c.step.id for c in calls] == ['plan', 'impl', 'tests', 'review', 'impl', 'tests', 'review']
    assert [c.state['task_index'] for c in calls] == [0, 0, 0, 0, 1, 1, 1]
    assert result['task_index'] == 2
    assert result['workflow_steps'] == 7
    assert result['status'] == 'ready_for_human_review'
    assert result['workflow_attempts'] == {'impl:0': 1, 'impl:1': 1}
    assert len(events) == 14
    assert all(set(payload) <= {'step_id', 'stage', 'status'} for _, payload in events)
    assert graph.config['recursion_limit'] == 404


@pytest.mark.parametrize('failure', ['rejection', 'failed_test'])
def test_retry_and_final_attempt_approval(case, failure):
    args, calls, _ = case
    args['definition']['steps'][1]['max_attempts'] = 2
    tests, reviews = [False, True, True], [False, True, True]
    normal = args['executors']['review']
    if failure == 'rejection':
        def reviewer(ctx):
            normal(ctx)
            return {'approved': reviews.pop(0), 'findings': []}
        args['executors']['review'] = reviewer
    else:
        def tester(ctx):
            normal(ctx)
            return {'passed': tests.pop(0)}
        args['executors']['test'] = tester
    result = compile_workflow(**args).invoke({})
    assert result['status'] == 'ready_for_human_review'
    assert [c.step.type for c in calls].count('implement') == 3
    assert result['workflow_attempts'] == {'impl:0': 2, 'impl:1': 1}


def test_retry_exhaustion_and_rejection_without_return(case):
    args, calls, _ = case
    args['definition']['steps'][1]['max_attempts'] = 2
    args['executors']['review'] = lambda ctx: {'approved': False, 'findings': []}
    result = compile_workflow(**args).invoke({})
    assert result['status'] == 'blocked'
    assert len([c for c in calls if c.step.type == 'implement']) == 2
    args['definition']['steps'][3].pop('on_reject')
    calls.clear()
    result = compile_workflow(**args).invoke({})
    assert result['status'] == 'blocked'
    assert len([c for c in calls if c.step.type == 'implement']) == 1


@pytest.mark.parametrize('failed_task', [0, 1])
def test_tests_after_review_block_without_repeating_task(case, failed_task):
    args, calls, _ = case
    steps = args['definition']['steps']
    steps[2], steps[3] = steps[3], steps[2]
    normal = args['executors']['test']
    def tester(ctx):
        normal(ctx)
        return {'passed': ctx.state['task_index'] != failed_task}
    args['executors']['test'] = tester
    result = compile_workflow(**args).invoke({})
    assert result['status'] == 'blocked'
    assert result['task_index'] == failed_task
    assert len([c for c in calls if c.step.type == 'implement']) == failed_task + 1


def test_optional_document_and_gates(case):
    args, calls, _ = case
    args['definition']['approval']['human_gate_after_plan'] = True
    args['definition']['steps'].extend([
        {'id': 'docs', 'type': 'document'}, {'id': 'final-human', 'type': 'human_gate'},
    ])
    args['bindings']['docs'] = {'provider_config_id': 'pc'}
    result = compile_workflow(**args).invoke({})
    assert result['status'] == 'ready_for_human_review'
    assert [c.step.type for c in calls] == ['plan', 'human_gate', 'implement', 'test', 'review',
                                          'implement', 'test', 'review', 'document', 'human_gate']


def test_gate_cannot_be_implicitly_approved(case):
    args, calls, _ = case
    args['definition']['approval']['human_gate_after_plan'] = True
    del args['executors']['human_gate']
    with pytest.raises(ValueError, match='human_gate'):
        compile_workflow(**args)
    assert calls == []
    args['executors']['human_gate'] = lambda ctx: {'approved': False}
    assert compile_workflow(**args).invoke({})['status'] == 'blocked'
    assert [c.step.id for c in calls] == ['plan']


def test_step_limit_cannot_be_overridden_by_langgraph_config(case):
    args, calls, _ = case
    args['definition']['limits']['max_total_steps'] = 1
    with pytest.raises(WorkflowLimitError, match='step limit'):
        compile_workflow(**args).invoke({}, config={'recursion_limit': 1000})
    assert [c.step.id for c in calls] == ['plan']


def test_deadline_is_checked_and_passed_to_host(case):
    args, calls, events = case
    now = [0.0]
    args['clock'] = lambda: now[0]
    args['definition']['limits']['max_duration_s'] = 1
    normal = args['executors']['plan']
    def slow(ctx):
        assert ctx.timeout_s == 1
        result = normal(ctx)
        now[0] = 2
        return result
    args['executors']['plan'] = slow
    with pytest.raises(WorkflowLimitError, match='duration limit'):
        compile_workflow(**args).invoke({})
    assert [c.step.id for c in calls] == ['plan']
    assert events[-1] == ('stage_finished', {'step_id': 'plan', 'stage': 'plan', 'status': 'failed'})


def test_definition_bindings_and_context_are_isolated(case):
    args, calls, _ = case
    args['bindings']['impl']['model'] = 'frozen-model'
    normal = args['executors']['implement']
    def adversarial(ctx):
        result = normal(ctx)
        assert ctx.binding.model == 'frozen-model'
        ctx.binding.model = 'changed-inside-call'
        ctx.step.max_attempts = 0
        ctx.state['workflow_steps'] = 100000
        return {**result, 'status': 'blocked', 'workflow_steps': 100000}
    args['executors']['implement'] = adversarial
    graph = compile_workflow(**args)
    args['definition']['steps'][1]['max_attempts'] = 0
    args['bindings']['impl']['model'] = 'changed-after-compile'
    args['provider_configs']['pc'] = 'other'
    first = graph.invoke({})
    second = graph.invoke({})
    assert first['status'] == second['status'] == 'ready_for_human_review'
    assert first['workflow_steps'] == second['workflow_steps'] == 7


@pytest.mark.parametrize('kind,payload', [
    ('plan', {'tasks': []}), ('plan', {'tasks': [{'id': 'same'}, {'id': 'same'}]}),
    ('review', {'approved': 'yes', 'findings': []}), ('review', {'approved': True}),
    ('test', {'passed': 1}), ('implement', 'not a dictionary'),
])
def test_invalid_stage_output_stops_execution(case, kind, payload):
    args, _, events = case
    args['executors'][kind] = lambda ctx: payload
    with pytest.raises(ValueError):
        compile_workflow(**args).invoke({})
    assert events[-1][1]['status'] == 'failed'


def test_unsupported_budget_fails_closed_and_configured_fallback_compiles(case):
    args, calls, _ = case
    args['definition']['limits']['budget_usd'] = 1.0
    with pytest.raises(ValueError, match='accounting'):
        compile_workflow(**args)
    args['definition']['limits']['budget_usd'] = None
    args['bindings']['plan']['fallbacks'] = [{'provider_config_id': 'pc', 'on': ['unavailable']}]
    compile_workflow(**args)
    assert calls == []


def test_compiler_validates_bindings_even_with_legacy_name(case):
    args, _, _ = case
    args['definition']['name'] = 'legacy-v1'
    args['bindings']['plan']['permission'] = 'workspace_write'
    with pytest.raises(ValidationError):
        compile_workflow(**args)


def test_topology_is_deterministic_and_follows_ids(case):
    args, _, _ = case
    def topology(graph):
        g = graph.get_graph()
        return sorted(g.nodes), sorted((e.source, e.target, e.conditional) for e in g.edges)
    first = topology(compile_workflow(**args))
    args['bindings']['plan']['model'] = 'another-model'
    assert topology(compile_workflow(**args)) == first
    args['definition']['steps'][1]['id'] = 'edited-id'
    args['definition']['steps'][3]['on_reject'] = 'edited-id'
    args['bindings']['edited-id'] = args['bindings'].pop('impl')
    assert topology(compile_workflow(**args)) != first


def test_no_per_task_block(case):
    args, _, _ = case
    args['definition']['steps'] = [args['definition']['steps'][0]]
    args['definition']['approval'].update(require_tests=False, require_reviewer=False)
    args['bindings'] = {'plan': args['bindings']['plan']}
    assert compile_workflow(**args).invoke({})['status'] == 'ready_for_human_review'


def test_review_before_edit_cannot_approve_later_changes(case):
    args, calls, _ = case
    steps = args['definition']['steps']
    steps[3].pop('on_reject')
    args['definition']['steps'] = [steps[0], steps[3], steps[1], steps[2]]
    result = compile_workflow(**args).invoke({})
    assert result['status'] == 'blocked'
    assert len([c for c in calls if c.step.type == 'implement']) == 1


@pytest.mark.parametrize('revalidate', [False, True])
def test_editing_document_requires_new_test_and_review_evidence(case, revalidate):
    args, _, _ = case
    args['definition']['steps'].append({'id': 'docs', 'type': 'document'})
    args['bindings']['docs'] = {'provider_config_id': 'pc', 'permission': 'workspace_write'}
    if revalidate:
        args['definition']['steps'].extend([
            {'id': 'final-tests', 'type': 'test'}, {'id': 'final-review', 'type': 'review'},
        ])
        args['bindings']['final-review'] = {'provider_config_id': 'pc'}
    result = compile_workflow(**args).invoke({})
    assert result['status'] == ('ready_for_human_review' if revalidate else 'blocked')


def test_initial_global_test_and_per_task_tests_can_both_pass(case):
    args, _, _ = case
    args['definition']['steps'].insert(1, {'id': 'baseline-tests', 'type': 'test'})
    assert compile_workflow(**args).invoke({})['status'] == 'ready_for_human_review'


def test_explicit_gate_after_plan_is_reused(case):
    args, calls, _ = case
    args['definition']['approval']['human_gate_after_plan'] = True
    args['definition']['steps'].insert(1, {'id': 'approve-plan', 'type': 'human_gate'})
    assert compile_workflow(**args).invoke({})['status'] == 'ready_for_human_review'
    assert [c.step.id for c in calls if c.step.type == 'human_gate'] == ['approve-plan']
