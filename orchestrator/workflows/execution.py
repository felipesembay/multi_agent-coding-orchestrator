"""AgentRuntime host for frozen workflows, without legacy binding exceptions.

Only already-validated CLI runtimes are supported. API providers, parameters,
gates and budgets need their own integrations before queueing.
"""
import math
import json
from pathlib import Path
import re
import shlex
import time

from .. import core
from ..providers.base import GenerationRequest, InvocationRequest, invoke_measured
from ..providers.context import review_context
from ..providers.errors import InvocationFailure
from ..resilience.ledger import StepLedger, classify_side_effects, next_step_attempt
from ..resilience.checkpointer import CheckpointError, checkpoint_config, open_checkpointer
from .compiler import compile_workflow
from .nodes import WorkflowLimitError, slot
from .snapshot import validate_snapshot


def execute_snapshot(repo, scope, *, run_id, snapshot, config, registry, clock=time.monotonic):
    snapshot = validate_snapshot(snapshot, registry=registry)
    if not re.fullmatch(r'run-[0-9a-f]{12}', run_id) or len(scope) > 100000:
        raise ValueError('Invalid workflow run identity or scope')

    ledger = StepLedger()

    def remaining(context):
        # Absolute deadline includes stage_started and any preceding Git work.
        left = min(context.timeout_s, snapshot.definition.limits.max_duration_s
                   - (clock() - context.state['workflow_started']))
        if left <= 0:
            raise WorkflowLimitError('Workflow duration limit reached')
        return left

    def agent(context):
        step, state = context.step, context.state
        frozen = snapshot.providers[context.binding.provider_config_id]
        model_provider = frozen.kind == 'model_provider'
        supplied_context = []
        task_obj = (
            state['plan']['tasks'][state['task_index']]
            if getattr(step, 'per_task', False) and state.get('plan')
            else None
        )
        task_id = task_obj.get('id') if isinstance(task_obj, dict) else None
        attempt_num = next_step_attempt(state['run_id'], step.id, task_id)
        side_effects = classify_side_effects(
            stage_type=step.type,
            permission=context.binding.permission if context.binding else None,
            adapter=context.adapter,
        )
        step_exec_id = ledger.start(
            run_id=state['run_id'],
            node=step.id,
            worktree=state['worktree'],
            task_id=task_id,
            attempt=attempt_num,
            role=step.role,
            side_effects=side_effects,
        )
        if step.type == 'plan':
            prompt = ('Return ONLY JSON: {"tasks":[{"id":"T1","title":"...",'
                      '"instructions":"...","acceptance":["..."],"tests":["..."]}]}. '
                      'Create 1-30 ordered, safe, independently verifiable tasks. '
                      'Keep implementation and its tests in the same task. '
                      'Do not edit files, execute commands or disclose secrets. Scope:\n' + state['scope'])
        elif step.type == 'implement':
            task = state['plan']['tasks'][state['task_index']] if step.per_task else state['plan']
            prompt = ('Implement the task in this worktree using native reading/editing tools. '
                      'Do not execute shell commands or tests. Do not commit, push, merge, '
                      'deploy, install packages, access secrets or edit outside this worktree. '
                      f'Task: {json.dumps(task)}\nPrevious stage outputs: '
                      + json.dumps(state['workflow_outputs'])[-16000:])
        elif step.type == 'review':
            task = state['plan']['tasks'][state['task_index']] if step.per_task else state['plan']
            tests = [state['workflow_outputs'][slot(s, state)] for s in snapshot.definition.steps
                     if s.type == 'test' and (not s.per_task or step.per_task)
                     and slot(s, state) in state['workflow_outputs']]
            if model_provider:
                try:
                    supplied_context = review_context(state['worktree'], runner=core.run_command,
                                                      timeout=lambda: min(600, remaining(context)))
                    diff, status = supplied_context[0].text, supplied_context[1].text
                except Exception:
                    ledger.fail(step_exec_id, error='Model review context unavailable', worktree=state['worktree'])
                    raise RuntimeError('Model review context unavailable') from None
            else:
                diff = core.run_command(['git', 'diff', '--no-ext-diff', 'HEAD'], state['worktree'], min(600, remaining(context)))
                status = core.run_command(['git', 'status', '--short'], state['worktree'], min(600, remaining(context)))
            prompt = ('Independently review this task against its acceptance criteria. '
                      'Do not edit files or execute tests/commands. Reject security defects '
                      'and regressions; do not reject work assigned to later tasks. '
                      'Inspect untracked files too. Return ONLY JSON: '
                      '{"approved":boolean,"findings":["..."],"test_suggestions":["..."]}. '
                      f'Task: {json.dumps(task)}\nAutomated tests: {json.dumps(tests)}\n'
                      f'Git status: {status}\nDiff excerpt: {diff[:16000]}')
        else:
            prompt = ('Document the completed work within the requested scope. '
                      'Respect the supplied permission; do not commit, merge, push, deploy, '
                      'execute shell commands, access secrets or edit outside the worktree. '
                      + state['scope'])
        timeout = min(config['agent_timeout'], max(1, math.ceil(remaining(context))))
        if model_provider:
            try:
                request = GenerationRequest(role=step.role, prompt=prompt, model=context.binding.model,
                    credential_ref=frozen.credential_ref, permission=context.binding.permission, timeout_s=timeout)
            except Exception:
                ledger.fail(step_exec_id, error='Invalid model generation request', worktree=state['worktree'])
                raise RuntimeError('Invalid model generation request') from None
        else:
            request = InvocationRequest(
                role=step.role, prompt=prompt, cwd=state['worktree'], model=context.binding.model,
                permission=context.binding.permission, timeout_s=timeout,
            )
        runtime = registry.get(context.adapter)
        record_failed = []
        def persist(call):
            from ..accounting.usage import record_usage
            metadata = {'step_id': step.id, 'task_index': state['task_index'],
                        'attempt': (state['workflow_attempts'].get(slot(step, state), 0)
                                    if step.type == 'implement' else 0) + context.invocation_attempt,
                        'chain_attempt': context.invocation_attempt, 'retry_of': context.retry_of}
            core.event(state, 'agent_call', {**call.model_dump(exclude={'usage': {'raw'}}), **metadata})
            usage = call.usage.model_dump(exclude={'raw', 'source'})
            core.event(state, 'usage_record', {**usage, **metadata,
                'call_id': call.call_id, 'provider': call.provider, 'role': call.role,
                'provider_config_id': context.binding.provider_config_id,
                'model': call.model, 'model_reported': call.model_reported,
                'duration_ms': call.duration_ms, 'error_code': call.error_code,
                'token_source': call.usage.source, 'billing_mode': runtime.manifest.billing_mode})
            record_usage(
                run_id=state['run_id'],
                call=call,
                billing_mode=runtime.manifest.billing_mode,
                provider_config_id=context.binding.provider_config_id,
                step_execution_id=step_exec_id,
                retry_of=context.retry_of,
            )
        def record(call):
            try:
                persist(call)
            except Exception:
                record_failed.append(True)
                raise
        try:
            result = invoke_measured(context.adapter, request,
                                     lambda: runtime.generate(request, supplied_context) if model_provider else runtime.invoke(request),
                                     record, call_id=context.call_id)
        except InvocationFailure as exc:
            ledger.fail(step_exec_id, error=exc.code, worktree=state['worktree'])
            if record_failed:
                raise RuntimeError('Could not persist workflow invocation metadata') from None
            raise
        except Exception:
            ledger.fail(step_exec_id, error='Workflow agent invocation failed', worktree=state['worktree'])
            raise RuntimeError('Workflow agent invocation failed') from None
        if result.error_code is not None:
            ledger.fail(step_exec_id, error=result.error_code, worktree=state['worktree'])
            # Error-bearing results are failures, never successful stage output.
            # No verified no-effects attestation: never select a fallback here.
            raise InvocationFailure(result.error_code)
        try:
            if step.type in ('plan', 'review'):
                payload = result.structured if result.structured is not None else core.extract_json(result.text)
                if step.type == 'plan':
                    tasks = payload.get('tasks')
                    if not isinstance(tasks, list) or any(not isinstance(t, dict) or not all(
                            key in t for key in ('id', 'title', 'instructions', 'acceptance')) for t in tasks):
                        raise ValueError('Invalid workflow plan tasks')
                    core.event(state, 'plan', payload)
                else:
                    if tests and not all(test['passed'] for test in tests):
                        payload = {**payload, 'approved': False}
                    core.event(state, 'review', {
                        'task': task.get('id'), **payload,
                        'test_result': {'passed': bool(tests) and all(test['passed'] for test in tests)},
                    })
                ledger.complete(step_exec_id, worktree=state['worktree'])
                return payload
            payload = {'output': result.text[-6000:]}
            if step.type == 'implement':
                core.event(state, 'implementation', {
                    'task': task.get('id'), 'output': payload['output'],
                    'attempt': state['workflow_attempts'].get(slot(step, state), 0) + context.invocation_attempt,
                })
            ledger.complete(step_exec_id, worktree=state['worktree'])
            return payload
        except Exception as exc:
            ledger.fail(step_exec_id, error=str(exc), worktree=state['worktree'])
            raise

    def test(context):
        step, state = context.step, context.state
        task_obj = (
            state['plan']['tasks'][state['task_index']]
            if getattr(step, 'per_task', False) and state.get('plan')
            else None
        )
        task_id = task_obj.get('id') if isinstance(task_obj, dict) else None
        step_exec_id = ledger.start(
            run_id=state['run_id'],
            node=step.id,
            worktree=state['worktree'],
            task_id=task_id,
            attempt=next_step_attempt(state['run_id'], step.id, task_id),
            role='tests',
            side_effects='exec',
        )
        timeout = min(config['test_timeout'], remaining(context))
        try:
            output = core.run_command(shlex.split(config['test_command']), context.state['worktree'],
                                      timeout)
            ledger.complete(step_exec_id, worktree=state['worktree'])
            return {'passed': True, 'output': output[-2500:]}
        except Exception:
            ledger.complete(step_exec_id, worktree=state['worktree'])
            return {'passed': False, 'error': 'Configured automated tests failed'}

    repo_path = Path(repo).resolve()
    with core.repository_lock(repo_path), open_checkpointer() as saver:
        saved_config = checkpoint_config(run_id)
        if saver.get_tuple(saved_config) is not None:
            raise CheckpointError('Existing checkpoint requires inspection before managed resume')
        graph = compile_workflow(snapshot.definition, snapshot.bindings,
                                 provider_configs={key: p.adapter for key, p in snapshot.providers.items()},
                                 registry=registry, executors={'plan': agent, 'implement': agent,
                                                              'review': agent, 'document': agent, 'test': test},
                                 event_sink=core.event, clock=clock, checkpointer=saver)
        worktree = core.prepare(repo_path, run_id)
        state = {'run_id': run_id, 'repo': str(repo_path), 'worktree': str(worktree), 'scope': scope}
        core.event(state, 'started', {'repo': str(repo_path), 'worktree': str(worktree),
                                    'workflow_version_id': snapshot.workflow_version_id,
                                    'workflow_digest': snapshot.digest()})
        result = graph.invoke(state,config={**saved_config,'metadata':{'workflow_digest':snapshot.digest()}},
                              durability='sync')
        core.event(result, 'finished' if result['status'] == 'ready_for_human_review' else 'blocked',
                   {'status': result['status'], 'worktree': str(worktree)})
        return result
