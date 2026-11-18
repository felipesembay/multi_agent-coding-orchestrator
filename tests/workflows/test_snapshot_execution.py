from contextlib import nullcontext
import json

import pytest

from orchestrator import core
from orchestrator.providers.base import InvocationResult
from orchestrator.workflows.execution import execute_snapshot
from orchestrator.workflows.nodes import WorkflowLimitError
from orchestrator.workflows.snapshot import load_snapshot


@pytest.mark.parametrize('exhaust', [False, True])
@pytest.mark.parametrize('target,event_delay', [('review', 0), ('review', 2), ('tests', 2), ('tests', 10)])
def test_review_git_and_runtime_share_remaining_deadline(snapshot_case, tmp_path, monkeypatch, exhaust, target, event_delay):
    selection, registry, _ = snapshot_case
    snapshot = load_snapshot(selection, registry=registry)
    snapshot.definition.limits.max_duration_s = 10
    now, git_timeouts, test_timeouts, calls = [0.0], [], [], []
    get = registry.get
    def runtime(adapter):
        provider = get(adapter)
        def invoke(request):
            calls.append(request)
            if request.role == 'planner':
                return InvocationResult(text=json.dumps({'tasks': [{
                    'id': 'T1', 'title': 'Task', 'instructions': 'Edit', 'acceptance': []}]}))
            if request.role == 'reviewer':
                return InvocationResult(text='{"approved":true,"findings":[]}')
            return InvocationResult(text='Done')
        provider.invoke = invoke
        return provider
    registry.get = runtime
    def command(argv, cwd, timeout=600):
        if argv[0] == 'git':
            git_timeouts.append(timeout)
            now[0] += 3 if len(git_timeouts) == 1 else (7 if exhaust else 2)
        else:
            test_timeouts.append(timeout)
        return ''
    monkeypatch.setattr(core, 'repository_lock', lambda repo: nullcontext())
    monkeypatch.setattr(core, 'prepare', lambda *args: tmp_path)
    def event(state, stage, payload):
        if stage == 'stage_started' and payload.get('step_id') == target:
            now[0] += event_delay
    monkeypatch.setattr(core, 'event', event)
    monkeypatch.setattr(core, 'run_command', command)
    def run():
        return execute_snapshot(str(tmp_path), 'scope', run_id='run-000000000001', snapshot=snapshot,
                                config={'agent_timeout': 100, 'test_timeout': 100, 'test_command': 'fake-tests'},
                                registry=registry, clock=lambda: now[0])
    if exhaust or event_delay == 10:
        with pytest.raises(WorkflowLimitError):
            run()
        assert [r.role for r in calls] == ['planner', 'implementer']
    else:
        assert run()['status'] == 'ready_for_human_review'
        assert calls[-1].timeout_s == 5 - event_delay
    if event_delay == 10:
        assert git_timeouts == test_timeouts == []
        return
    assert git_timeouts == [10 - event_delay, 7 - event_delay]
    assert test_timeouts == [10 - event_delay if target == 'tests' else 10]
