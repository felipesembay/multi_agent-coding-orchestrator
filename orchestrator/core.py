from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import uuid
from contextlib import closing, contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .providers.base import AgentCall, InvocationRequest, invoke_measured
from .providers.bindings import AgentBindings, legacy_bindings, validate_bindings
from .providers.registry import ProviderRegistry
from .providers.runtimes.antigravity import AntigravityRuntime
from .providers.runtimes.claude_code import ClaudeCodeRuntime
from .providers.runtimes.codex_cli import CodexCliRuntime
from .repository_lock import lock_fd, repository_lock


class State(TypedDict, total=False):
    run_id: str
    repo: str
    worktree: str
    scope: str
    plan: dict
    task_index: int
    attempts: int
    review: dict
    status: str
    error: str
    managed: bool
    bindings: dict


SCHEMA = '''
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    at TEXT DEFAULT CURRENT_TIMESTAMP,
    stage TEXT,
    payload TEXT
);
'''


def db_path() -> str:
    return os.environ.get(
        'ORCH_DB',
        str(Path.home() / '.local/state/multi-agent-orchestrator/events.db'),
    )


def db(path: str):
    path = str(Path(path).expanduser())
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def event(state: State, stage: str, payload: object):
    with db(db_path()) as conn:
        conn.execute(
            'INSERT INTO events(run_id,stage,payload) VALUES(?,?,?)',
            (state['run_id'], stage, json.dumps(payload, ensure_ascii=False)),
        )


def run_command(argv: list[str], cwd: str, timeout: int = 600,
                env: dict | None = None) -> str:
    if not shutil.which(argv[0]):
        raise RuntimeError(f'Executable missing: {argv[0]}')
    try:
        result = subprocess.run(
            argv, cwd=cwd, text=True, capture_output=True,
            timeout=timeout, env=env, check=False,
            pass_fds=() if lock_fd.get() is None else (lock_fd.get(),),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'{argv[0]} timed out after {timeout}s') from exc
    if result.returncode:
        details = (result.stderr or result.stdout)[-2500:]
        raise RuntimeError(f'{argv[0]} exited {result.returncode}: {details}')
    return result.stdout


def extract_json(value: str) -> dict:
    try:
        result = json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', value, re.S)
        if not match:
            raise ValueError('Agent response was not valid JSON')
        result = json.loads(match.group(1))
    if not isinstance(result, dict):
        raise ValueError('Expected a JSON object from agent')
    return result


# Scope metadata to a run without changing public facade signatures or patch points.
_agent_context = ContextVar('agent_context', default=None)
_provider_registry = ContextVar('provider_registry', default=None)


@contextmanager
def _using_provider_registry(registry):
    token = _provider_registry.set(registry)
    try:
        yield
    finally:
        _provider_registry.reset(token)


def _registry():
    return _provider_registry.get() or ProviderRegistry()


def _resolved_bindings(state=None):
    saved = state.get('bindings') if state else None
    config = AgentBindings.model_validate(saved) if saved is not None else legacy_bindings()
    return validate_bindings(config, _registry())



@contextmanager
def _agent_call_context(state, role):
    token = _agent_context.set((state, role))
    try:
        yield
    finally:
        _agent_context.reset(token)


def _request(**kwargs):
    context = _agent_context.get()
    return InvocationRequest(role=context[1] if context else 'legacy', **kwargs)


def _record_agent_call(call: AgentCall):
    context = _agent_context.get()
    if context is not None and context[0] is not None:
        # Explicitly exclude raw usage, even when future parsers populate it.
        event(context[0], 'agent_call', call.model_dump(exclude={'usage': {'raw'}}))


def claude(prompt: str, cwd: str, timeout: int = 600) -> str:
    return ClaudeCodeRuntime(run_command, observer=_record_agent_call).invoke(_request(
        prompt=prompt, cwd=cwd, timeout_s=timeout, permission='workspace_write',
    )).text


def codex(prompt: str, cwd: str, timeout: int = 600) -> str:
    return CodexCliRuntime(run_command, observer=_record_agent_call).invoke(_request(
        prompt=prompt, cwd=cwd, timeout_s=timeout, permission='read_only',
    )).text


def antigravity(
    prompt: str,
    cwd: str,
    timeout: int = 900,
    mode: str = 'plan',
    model: str | None = None
) -> str:
    """Compatibility facade retaining legacy arguments and patch points."""
    if mode not in ('plan', 'accept-edits'):
        raise ValueError(f'Invalid Antigravity mode: {mode}')
    return AntigravityRuntime(run_command, observer=_record_agent_call).invoke(_request(
        prompt=prompt, cwd=cwd, timeout_s=timeout, model=model,
        permission='read_only' if mode == 'plan' else 'workspace_write',
    )).text


def coding_agent(prompt: str, cwd: str, role: str, state: State | None = None) -> str:
    """Select the legacy provider with metadata scoped to this run and role."""
    with _agent_call_context(state, role):
        return _coding_agent(prompt, cwd, role, state)


def _invoke_binding(binding, prompt, cwd, role, timeout):
    # Preserve the legacy facade patch points and their exact call arguments.
    if binding.adapter == 'claude_code':
        return claude(prompt, cwd, timeout)
    if binding.adapter == 'codex_cli':
        return codex(prompt, cwd, timeout)
    if binding.adapter == 'antigravity':
        return antigravity(prompt, cwd, timeout=timeout,
                           mode='plan' if binding.permission == 'read_only' else 'accept-edits',
                           model=binding.model)
    runtime = _registry().get(binding.adapter)
    request = InvocationRequest(role=role, prompt=prompt, cwd=cwd, model=binding.model,
                                permission=binding.permission, timeout_s=timeout)
    return invoke_measured(binding.adapter, request, lambda: runtime.invoke(request), _record_agent_call).text


def _coding_agent(prompt: str, cwd: str, role: str, state: State | None = None) -> str:
    if role not in ('planner', 'implementer'):
        raise ValueError(f'Invalid agent role: {role}')
    config = _resolved_bindings(state)
    binding = getattr(config, role)
    try:
        return _invoke_binding(binding, prompt, cwd, role, config.agent_timeout)
    except RuntimeError as exc:
        quota_errors = ('rate limit', 'rate_limit', 'usage limit', 'usage_limit',
                        'quota exceeded', 'out of extra usage', 'hit your limit',
                        'you have reached your limit')
        if (role != 'planner' or config.planner_fallback is None
                or not any(marker in str(exc).lower() for marker in quota_errors)):
            raise
        if state is not None:
            event(state, 'agent_fallback', {
                'role': role, 'primary': 'claude', 'fallback': 'antigravity', 'reason': 'usage_limit',
            })
        print('[orchestrator] Claude usage limit detected. Falling back to Antigravity.', flush=True)
        return _invoke_binding(config.planner_fallback, prompt, cwd, role, config.agent_timeout)


def plan(state: State) -> State:
    if state.get('managed'):
        event(state, 'stage_started', {'stage': 'plan', 'role': 'planner'})
    prompt = (
        'You are a technical lead. Return ONLY JSON with '
        '{"tasks":[{"id":"T1","title":"...","instructions":"...",'
        '"acceptance":["..."],"tests":["..."]}]}. '
        'Tasks must be ordered by dependency, small, concrete, safe. '
        'Each task must be independently verifiable before proceeding. '
        'Include relevant automated tests in the SAME task as the implementation. '
        'Do not create a separate later task solely for tests of earlier code. '
        'All tasks must preserve passing tests from previous tasks. '
        'No shell commands in JSON. Never request secret disclosure. Scope:\n'
        + state['scope']
    )
    result = extract_json(coding_agent(prompt, state['worktree'], 'planner', state=state))
    tasks = result.get('tasks')
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 30:
        raise ValueError('Expected 1-30 tasks')
    ids = set()
    for task in tasks:
        if not isinstance(task, dict) or not all(
            key in task for key in ('id', 'title', 'instructions', 'acceptance')
        ):
            raise ValueError('Invalid task')
        if not isinstance(task['id'], str) or task['id'] in ids:
            raise ValueError('Missing or duplicate task ID')
        ids.add(task['id'])
    event(state, 'plan', result)
    return {'plan': result, 'task_index': 0, 'attempts': 0,
            'review': {}, 'status': 'running'}


def implement(state: State) -> State:
    if state.get('managed'):
        event(state, 'stage_started', {'stage': 'implementation', 'role': 'implementer'})
    task = state['plan']['tasks'][state['task_index']]
    attempts = state.get('attempts', 0)
    feedback = state.get('review', {}) if attempts else {}
    prompt = (
        'Implement this task in the current repository. You may edit files. '
        'Do not execute ANY shell or terminal commands, including tests, '
        'ls, cat, pwd, git, or package managers. '
        'Use only your native file editing and reading tools. '
        'The orchestrator will execute tests independently. '
        'Do not commit, push, access secrets, deploy, install packages, '
        'or run destructive commands. Do not modify files outside this repository. '
        f'Task JSON: {json.dumps(task)}\n'
        f'Previous QA feedback: {json.dumps(feedback)}\n'
        'Summarize changed files and test commands in your final response.'
    )
    # A failed agent call is NOT counted as a completed implementation.
    result = coding_agent(prompt, state['worktree'], 'implementer', state=state)
    event(state, 'implementation', {
        'task': task['id'], 'attempt': attempts + 1, 'output': result[-6000:],
    })
    return {'attempts': attempts + 1}


def review(state: State) -> State:
    if state.get('managed'):
        event(state, 'stage_started', {'stage': 'review', 'role': 'reviewer'})
    task = state['plan']['tasks'][state['task_index']]
    worktree = state['worktree']
    test_cmd = os.getenv('ORCH_TEST_COMMAND', '').strip()
    if test_cmd:
        try:
            output = run_command(
                shlex.split(test_cmd), worktree,
                int(os.getenv('TEST_TIMEOUT', '300')),
            )
            test_result = {'passed': True, 'output': output[-2500:]}
        except Exception as exc:
            test_result = {'passed': False, 'error': str(exc)[-2500:]}
    else:
        test_result = {
            'passed': False, 'error': 'ORCH_TEST_COMMAND not configured',
        }

    diff = run_command(['git', 'diff', '--no-ext-diff', 'HEAD'], worktree)
    status = run_command(['git', 'status', '--short'], worktree)
    prompt = (
        'You are independent QA. Review the repository and task. '
        'This project is implemented incrementally through an ordered task plan. '
        'Review the current task against its own instructions and acceptance criteria. '
        'Do not reject a task solely because functionality explicitly assigned '
        'to a later task has not yet been implemented. '
        'However, reject genuine defects in the current implementation, '
        'including invalid data handling, security issues, and broken task logic. '
        'Distinguish blocking defects from future integration work in your findings. '
        'Do not edit files. Do not run tests yourself; the orchestrator '
        'has already executed the configured automated tests. '
        'Use supplied test results as evidence, but independently inspect '
        'the code for correctness, security, regressions, and acceptance gaps. '
        'Untracked files may be part of the implementation; inspect them. '
        'Do not reject solely because files are untracked. '
        'Return ONLY JSON: {"approved":boolean,"findings":["..."],'
        '"test_suggestions":["..."]}. '
        'Approve only if the implementation satisfies the task and '
        'the supplied test results support that conclusion.\n'
        f'Task: {json.dumps(task)}\n'
        f'Upcoming tasks: {json.dumps(state["plan"]["tasks"][state["task_index"] + 1:])}\n'
        f'Git status: {status}\n'
        f'Diff excerpt: {diff[:16000]}\n'
        f'Automated test results: {json.dumps(test_result)}'
    )
    config = _resolved_bindings(state)
    with _agent_call_context(state, 'reviewer'):
        result = extract_json(_invoke_binding(
            config.reviewer, prompt, worktree, 'reviewer', config.agent_timeout,
        ))
    if not isinstance(result.get('approved'), bool) or not isinstance(
        result.get('findings'), list
    ):
        raise ValueError('Invalid QA output')
    result['test_result'] = test_result
    if not test_result['passed']:
        result['approved'] = False
        result['findings'].append('Configured automated tests did not pass')
    event(state, 'review', {'task': task['id'], **result})
    return {'review': result}


def decide(state: State) -> str:
    if state['review']['approved']:
        return 'next'
    if state['attempts'] >= int(os.getenv('MAX_ATTEMPTS', '3')):
        return 'blocked'
    return 'retry'


def advance(state: State) -> State:
    return {'task_index': state['task_index'] + 1,
            'attempts': 0, 'review': {}}


def more(state: State) -> str:
    return ('continue' if state['task_index'] < len(state['plan']['tasks'])
            else 'finish')


def finish(state: State) -> State:
    event(state, 'finished', {
        'status': 'ready_for_human_review', 'worktree': state['worktree'],
    })
    return {'status': 'ready_for_human_review'}


def blocked(state: State) -> State:
    event(state, 'blocked', {
        'task_index': state['task_index'], 'review': state.get('review'),
    })
    return {'status': 'blocked'}


def graph(entry_point: str = 'plan'):
    if entry_point not in ('plan', 'implement', 'review'):
        raise ValueError(f'Invalid graph entry point: {entry_point}')
    g = StateGraph(State)
    for name, fn in (
        ('plan', plan), ('implement', implement), ('review', review),
        ('advance', advance), ('finish', finish), ('blocked', blocked),
    ):
        g.add_node(name, fn)
    g.set_entry_point(entry_point)
    g.add_edge('plan', 'implement')
    g.add_edge('implement', 'review')
    g.add_conditional_edges('review', decide, {
        'next': 'advance', 'retry': 'implement', 'blocked': 'blocked',
    })
    g.add_conditional_edges('advance', more, {
        'continue': 'implement', 'finish': 'finish',
    })
    g.add_edge('finish', END)
    g.add_edge('blocked', END)
    return g.compile()


def prepare(repo: Path, run_id: str) -> Path:
    repo = repo.resolve()
    if not (repo / '.git').exists():
        raise ValueError('Target must be a git repository')
    if run_command(['git', 'status', '--porcelain'], str(repo)).strip():
        raise ValueError('Commit or stash changes before orchestration (clean worktree required)')
    base = Path(os.getenv(
        'ORCH_WORKTREES', str(repo.parent / (repo.name + '-agent-worktrees')),
    )).resolve()
    base.mkdir(parents=True, exist_ok=True)
    target = base / run_id
    run_command(['git', 'worktree', 'add', '-b', f'agent/{run_id}',
                 str(target), 'HEAD'], str(repo))
    return target


def _invoke(state: State, entry_point: str) -> State:
    try:
        return graph(entry_point=entry_point).invoke(
            state, config={'recursion_limit': 250},
        )
    except Exception as exc:
        # The error event preserves auditability without pretending that
        # the failed agent call completed or that its files were unchanged.
        event(state, 'error', {
            'message': str(exc)[-2500:], 'entry_point': entry_point,
        })
        raise


def execute(repo: str, scope_file: str) -> State:
    scope = Path(scope_file).resolve().read_text(encoding='utf-8')
    return execute_scope(repo, scope)


def execute_scope(repo: str, scope: str, run_id: str | None = None, *, managed: bool = False,
                  bindings: AgentBindings | dict | None = None, provider_registry=None) -> State:
    """Shared entry point: CLI reads its file; the manager supplies saved requirements."""
    if len(scope) > 100_000:
        raise ValueError('Scope exceeds 100k characters')
    run_id = run_id or 'run-' + uuid.uuid4().hex[:12]
    if not re.fullmatch(r'run-[0-9a-f]{12}', run_id):
        raise ValueError('Invalid run_id')
    registry = provider_registry or _registry()
    resolved = validate_bindings(
        AgentBindings.model_validate(bindings.model_dump() if isinstance(bindings, AgentBindings) else bindings)
        if bindings is not None else legacy_bindings(), registry,
    )
    repo_path = Path(repo).resolve()
    with _using_provider_registry(registry), repository_lock(repo_path):
        worktree = prepare(repo_path, run_id)
        state: State = {
            'run_id': run_id, 'repo': str(repo_path),
            'worktree': str(worktree), 'scope': scope, 'managed': managed,
            'bindings': resolved.model_dump(),
        }
        event(state, 'started', {
            'repo': str(repo_path), 'worktree': str(worktree), 'bindings': resolved.model_dump(),
        })
        return _invoke(state, 'plan')


def _load_events(run_id: str):
    with db(db_path()) as conn:
        rows = conn.execute(
            'SELECT stage,payload FROM events WHERE run_id=? ORDER BY id ASC',
            (run_id,),
        ).fetchall()
    return [(stage, json.loads(payload)) for stage, payload in rows]


def _recovery_position(events: list, tasks: list) -> tuple[int, int, dict, str]:
    """Reconstruct the next action from completed implementation/review events.

    Historical runs do not have LangGraph checkpoints. This routine handles
    the known event protocol and refuses ambiguous/inconsistent histories.
    """
    ids = [task['id'] for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate task IDs in saved plan')
    history = {task_id: {'implementations': [], 'reviews': []} for task_id in ids}
    for stage, payload in events:
        if stage in ('implementation', 'review'):
            task_id = payload.get('task')
            if task_id not in history:
                raise ValueError(f'Unknown task in event history: {task_id}')
            key = 'implementations' if stage == 'implementation' else 'reviews'
            history[task_id][key].append(payload)

    for index, task_id in enumerate(ids):
        impl = history[task_id]['implementations']
        reviews = history[task_id]['reviews']
        if any(r.get('approved') is True for r in reviews):
            if not impl:
                raise ValueError(f'Approved task {task_id} has no implementation')
            continue
        # The first task without an approved review is the only recoverable task.
        if any(history[later]['implementations'] or history[later]['reviews']
               for later in ids[index + 1:]):
            raise ValueError('Inconsistent history: later tasks started before approval')
        if len(reviews) > len(impl):
            raise ValueError('More reviews than implementations')
        if not impl:
            return index, 0, {}, 'implement'
        attempts = len(impl)
        if len(reviews) < len(impl):
            # Implementation finished, but QA never completed.
            return index, attempts, {}, 'review'
        last_review = reviews[-1]
        if not isinstance(last_review.get('approved'), bool):
            raise ValueError('Invalid review event')
        if attempts >= int(os.getenv('MAX_ATTEMPTS', '3')):
            # A blocked task can be re-reviewed after fixing its environment.
            # Do not reset the attempt count, preventing unbounded retries.
            return index, attempts, last_review, 'review'
        return index, attempts, last_review, 'implement'
    raise ValueError('All tasks have approved reviews; no pending task')


def resume(run_id: str, dry_run: bool = False) -> State:
    if not re.fullmatch(r'run-[0-9a-f]{12}', run_id):
        raise ValueError('Invalid run_id')
    with closing(db(db_path())) as conn:
        has_manager = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='managed_runs'").fetchone()
        if has_manager and conn.execute('SELECT 1 FROM managed_runs WHERE run_id=?', (run_id,)).fetchone():
            raise ValueError('Execução gerenciada: inspecione a worktree e autorize uma nova execução pelo projeto. Retomada gerenciada ainda não está disponível.')
    events = _load_events(run_id)
    if not events:
        raise ValueError(f'Run not found: {run_id}')
    if any(stage == 'finished' for stage, _ in events):
        raise ValueError('Run already finished')
    started = next((p for stage, p in events if stage == 'started'), None)
    planned = next((p for stage, p in events if stage == 'plan'), None)
    if started is None or planned is None:
        raise ValueError('Missing start or plan event')
    tasks = planned.get('tasks')
    if not isinstance(tasks, list) or not tasks or any(
        not isinstance(task, dict) or not isinstance(task.get('id'), str)
        for task in tasks
    ):
        raise ValueError('Invalid saved plan')

    repo = Path(started['repo']).resolve()
    worktree = Path(started['worktree']).resolve()
    if not repo.is_dir() or not worktree.is_dir():
        raise ValueError('Repository or worktree no longer exists')
    expected_base = Path(os.getenv(
        'ORCH_WORKTREES', str(repo.parent / (repo.name + '-agent-worktrees')),
    )).resolve()
    if worktree != expected_base / run_id:
        raise ValueError('Unexpected worktree path')
    actual_root = Path(run_command(
        ['git', 'rev-parse', '--show-toplevel'], str(worktree),
    ).strip()).resolve()
    if actual_root != worktree:
        raise ValueError('Worktree Git root mismatch')

    task_index, attempts, feedback, entry_point = _recovery_position(events, tasks)
    state: State = {
        'run_id': run_id, 'repo': str(repo), 'worktree': str(worktree),
        'scope': '', 'plan': planned, 'task_index': task_index,
        'attempts': attempts, 'review': feedback, 'status': 'resuming',
        'bindings': (AgentBindings.model_validate(started['bindings'])
                     if 'bindings' in started else legacy_bindings()).model_dump(),
    }
    if dry_run:
        return {**state, 'entry_point': entry_point}

    with repository_lock(repo):
        event(state, 'resumed', {
            'task_index': task_index, 'task': tasks[task_index]['id'],
            'attempts': attempts, 'entry_point': entry_point,
        })
        return _invoke(state, entry_point)
