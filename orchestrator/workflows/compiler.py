"""Deterministic linear workflow compilation with bounded per-task returns.

New definitions require trusted executors supplied by the host. This compiler
does not select presets, load plugins, invoke CLIs or implement persistence.
"""
from copy import deepcopy
import time

from langgraph.graph import END, StateGraph

from .nodes import WorkflowState, check_time, make_step_node, slot
from .schema import HumanGateStep, StepBinding, WorkflowDefinition
from .validation import validate_workflow


# Private legacy layout: data captured from core.graph before extraction. It is
# not selected by user workflow.name and is never passed to strict v2 validation.
# The combined legacy review includes tests, so splitting it would break resume
# entries, event ordering and subprocess behavior.
_LEGACY_NODES = ('plan', 'implement', 'review', 'advance', 'finish', 'blocked')
_LEGACY_EDGES = (('plan', 'implement'), ('implement', 'review'), ('finish', END), ('blocked', END))
_LEGACY_BRANCHES = (
    ('review', 'decide', (('next', 'advance'), ('retry', 'implement'), ('blocked', 'blocked'))),
    ('advance', 'more', (('continue', 'implement'), ('finish', 'finish'))),
)


def compile_legacy(*, state_schema, handlers, entry_point='plan'):
    """Host-only compatibility entry: existing callbacks and permissions intact."""
    if entry_point not in ('plan', 'implement', 'review'):
        raise ValueError(f'Invalid graph entry point: {entry_point}')
    graph = StateGraph(state_schema)
    for name in _LEGACY_NODES:
        graph.add_node(name, handlers[name])
    graph.set_entry_point(entry_point)
    for source, target in _LEGACY_EDGES:
        graph.add_edge(source, target)
    for source, router, routes in _LEGACY_BRANCHES:
        graph.add_conditional_edges(source, handlers[router], dict(routes))
    return graph.compile()


def compile_workflow(definition, bindings, *, provider_configs, registry, executors,
                     event_sink=None, clock=time.monotonic):
    """Compile with executors keyed by type: execute(StepContext) -> dict payload.

    The host is responsible for runtime timeouts (context.timeout_s is remaining
    workflow time) and approval provenance. Gate execution is mandatory and
    explicit; there is no automatic approval or implicit CLI execution.
    """
    definition = WorkflowDefinition.model_validate(
        definition.model_dump() if isinstance(definition, WorkflowDefinition) else deepcopy(definition))
    if definition.approval.human_gate_after_plan and not (
            len(definition.steps) > 1 and definition.steps[1].type == 'human_gate'
            and not definition.steps[1].per_task):
        used = {s.id for s in definition.steps}
        gate_id = 'plan-approval'
        while gate_id in used:
            gate_id += '-gate'
        definition.steps.insert(1, HumanGateStep(id=gate_id, type='human_gate'))
    handlers = dict(executors)
    for step in definition.steps:
        if not callable(handlers.get(step.type)):
            raise ValueError(f'Missing executor for stage type: {step.type}')
    if definition.limits.budget_usd is not None:
        raise ValueError('Budget enforcement requires the accounting integration')
    definition = validate_workflow(definition, bindings, provider_configs=provider_configs, registry=registry)
    frozen_bindings = {key: StepBinding.model_validate(value.model_dump() if isinstance(value, StepBinding) else deepcopy(value))
                       for key, value in bindings.items()}
    if any(binding.fallbacks for binding in frozen_bindings.values()):
        raise ValueError('Configurable fallback execution requires V2-WF-010')
    adapters = dict(provider_configs)
    steps = definition.steps
    task_steps = [s for s in steps if s.per_task]
    by_id = {s.id: s for s in steps}
    graph = StateGraph(WorkflowState)

    def emit(state, stage, payload):
        if event_sink is not None:
            event_sink(deepcopy(state), stage, deepcopy(payload))

    def initialize(state):
        return {'workflow_started': clock(), 'workflow_steps': 0, 'workflow_attempts': {},
                'workflow_outputs': {}, 'workflow_revision': 0, 'workflow_evidence': {},
                'task_index': 0, 'status': 'running'}

    def accepted(stage, state, fresh=True):
        key = slot(stage, state)
        output = state['workflow_outputs'].get(key, {})
        field = 'passed' if stage.type == 'test' else 'approved'
        return (output.get(field) is True and (not fresh or stage.type == 'human_gate'
                or state['workflow_evidence'].get(key) == state['workflow_revision']))

    def block_passed(state):
        return all(accepted(s, state) for s in task_steps if s.type in ('test', 'review', 'human_gate'))

    def review_route(step, next_node):
        # Tests preceding this review are mandatory even if a reviewer says yes.
        prior_tests = [s for s in steps[:steps.index(step)] if s.type == 'test'
                       and (not s.per_task or step.per_task)]

        def route(state):
            if accepted(step, state) and all(accepted(s, state, fresh=False) for s in prior_tests):
                return next_node
            if step.on_reject:
                target = by_id[step.on_reject]
                if state['workflow_attempts'].get(slot(target, state), 0) < target.max_attempts:
                    return target.id
            return '__wf_blocked'
        return route

    graph.add_node('__wf_initialize', initialize)
    graph.set_entry_point('__wf_initialize')
    graph.add_edge('__wf_initialize', steps[0].id)
    for index, step in enumerate(steps):
        binding = frozen_bindings.get(step.id)
        adapter = adapters[binding.provider_config_id] if binding else None
        graph.add_node(step.id, make_step_node(step, binding, adapter, handlers[step.type], definition, clock, emit))
        next_node = steps[index + 1].id if index + 1 < len(steps) else '__wf_finish'
        if task_steps and step.id == task_steps[-1].id:
            next_node = '__wf_advance'
        if step.type == 'review':
            routes = {next_node: next_node, '__wf_blocked': '__wf_blocked'}
            if step.on_reject:
                routes[step.on_reject] = step.on_reject
            graph.add_conditional_edges(step.id, review_route(step, next_node), routes)
        elif step.type == 'human_gate':
            def gate_route(state, current=step, following=next_node):
                return following if accepted(current, state) else '__wf_blocked'
            graph.add_conditional_edges(step.id, gate_route, {next_node: next_node, '__wf_blocked': '__wf_blocked'})
        else:
            graph.add_edge(step.id, next_node)

    if task_steps:
        after_block = steps.index(task_steps[-1]) + 1
        suffix = steps[after_block].id if after_block < len(steps) else '__wf_finish'

        def advance(state):
            check_time(definition, state, clock)
            passed = block_passed(state)
            return {'task_index': state['task_index'] + int(passed), 'workflow_block_passed': passed}

        def more(state):
            # A failed block does not advance, even when tests follow review.
            if not state['workflow_block_passed']:
                return '__wf_blocked'
            return task_steps[0].id if state['task_index'] < len(state['plan']['tasks']) else suffix

        graph.add_node('__wf_advance', advance)
        graph.add_conditional_edges('__wf_advance', more, {
            task_steps[0].id: task_steps[0].id, suffix: suffix, '__wf_blocked': '__wf_blocked',
        })

    def finish(state):
        check_time(definition, state, clock)
        for step in steps:
            if step.type not in ('test', 'review', 'human_gate'):
                continue
            indices = range(len(state['plan']['tasks'])) if step.per_task else [state['task_index']]
            # Prior tasks were approved at their own block boundary. Keep that
            # history, while requiring fresh evidence for the last repo write.
            if any(not accepted(step, {**state, 'task_index': i}, fresh=False) for i in indices):
                return {'status': 'blocked'}
        for kind in ('test', 'review'):
            relevant = [s for s in steps if s.type == kind]
            if relevant and not any(
                key.startswith(s.id + ':') and revision == state['workflow_revision']
                for s in relevant for key, revision in state['workflow_evidence'].items()
            ):
                return {'status': 'blocked'}
        return {'status': 'ready_for_human_review'}

    graph.add_node('__wf_finish', finish)
    graph.add_node('__wf_blocked', lambda state: {'status': 'blocked'})
    graph.add_edge('__wf_finish', END)
    graph.add_edge('__wf_blocked', END)
    # One advance at most per declared stage execution plus fixed control nodes.
    return graph.compile().with_config(recursion_limit=2 * definition.limits.max_total_steps + 4)
