"""Stage envelopes for trusted host executors, independent of CLI adapters.

Executors receive copies of the frozen stage/binding and a state snapshot. They
return a stage payload, never orchestration counters or routing decisions.
"""
from copy import deepcopy
from dataclasses import dataclass
from typing import Optional, TypedDict

from .schema import StepBinding


class WorkflowState(TypedDict, total=False):
    run_id: str
    repo: str
    worktree: str
    scope: str
    plan: dict
    task_index: int
    status: str
    workflow_steps: int
    workflow_started: float
    workflow_attempts: dict
    workflow_outputs: dict
    workflow_block_passed: bool
    workflow_revision: int
    workflow_evidence: dict


class WorkflowLimitError(RuntimeError):
    pass


@dataclass(frozen=True)
class StepContext:
    step: object
    binding: Optional[StepBinding]
    adapter: Optional[str]
    state: dict
    timeout_s: float


def slot(step, state):
    return f'{step.id}:{state["task_index"] if step.per_task else "global"}'


def check_time(definition, state, clock):
    remaining = definition.limits.max_duration_s - (clock() - state['workflow_started'])
    if remaining <= 0:
        raise WorkflowLimitError('Workflow duration limit reached')
    return remaining


def validate_payload(step, payload, needs_tasks):
    if not isinstance(payload, dict):
        raise ValueError('Stage executor must return a dictionary payload')
    if step.type == 'plan' and needs_tasks:
        tasks = payload.get('tasks')
        if (not isinstance(tasks, list) or not 1 <= len(tasks) <= 30
                or any(not isinstance(t, dict) or not isinstance(t.get('id'), str) for t in tasks)
                or len({t['id'] for t in tasks}) != len(tasks)):
            raise ValueError('Expected 1-30 tasks with unique string IDs')
    if step.type == 'test' and type(payload.get('passed')) is not bool:
        raise ValueError('Test executor must return boolean passed')
    if step.type in ('review', 'human_gate') and type(payload.get('approved')) is not bool:
        raise ValueError('Approval executor must return boolean approved')
    if step.type == 'review' and not isinstance(payload.get('findings'), list):
        raise ValueError('Review executor must return findings list')


def make_step_node(step, binding, adapter, executor, definition, clock, emit):
    needs_tasks = any(s.per_task for s in definition.steps)

    def run(state):
        remaining = check_time(definition, state, clock)
        if state['workflow_steps'] >= definition.limits.max_total_steps:
            raise WorkflowLimitError('Workflow step limit reached')
        key = slot(step, state)
        attempts = dict(state['workflow_attempts'])
        if step.type == 'implement' and attempts.get(key, 0) >= step.max_attempts:
            raise WorkflowLimitError('Implementation attempt limit reached')
        metadata = {'step_id': step.id, 'stage': step.type}
        emit(state, 'stage_started', metadata)
        try:
            payload = deepcopy(executor(StepContext(
                step=step.model_copy(deep=True),
                binding=binding.model_copy(deep=True) if binding else None,
                adapter=adapter, state=deepcopy(state), timeout_s=remaining,
            )))
            validate_payload(step, payload, needs_tasks)
            check_time(definition, state, clock)
        except Exception:
            emit(state, 'stage_finished', {**metadata, 'status': 'failed'})
            raise
        outputs = {**state['workflow_outputs'], key: payload}
        revision = state['workflow_revision'] + int(binding is not None and binding.permission == 'workspace_write')
        evidence = dict(state['workflow_evidence'])
        if step.type in ('test', 'review'):
            evidence[key] = revision
        if step.type == 'implement':
            attempts[key] = attempts.get(key, 0) + 1
        update = {'workflow_steps': state['workflow_steps'] + 1,
                  'workflow_outputs': outputs, 'workflow_attempts': attempts,
                  'workflow_revision': revision, 'workflow_evidence': evidence}
        if step.type == 'plan':
            update['plan'] = payload
        emit(state, 'stage_finished', {**metadata, 'status': 'completed'})
        return update

    return run
