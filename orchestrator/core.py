from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import uuid
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph


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


def claude(prompt: str, cwd: str, timeout: int = 600) -> str:
    return run_command(
        ['claude', '-p', '--permission-mode', 'acceptEdits', prompt],
        cwd, timeout,
    )


def codex(prompt: str, cwd: str, timeout: int = 600) -> str:
    return run_command(
        ['codex', 'exec', '--sandbox', 'read-only', prompt],
        cwd, timeout,
    )

def antigravity(
    prompt: str,
    cwd: str,
    timeout: int = 900,
    mode: str = 'plan',
    model: str | None = None
) -> str:
    """
    Executa o Antigravity CLI e retorna somente
    o texto produzido pelo agente.
    """
    if mode not in ('plan', 'accept-edits'):
        raise ValueError(f'Invalid Antigravity mode: {mode}')

    if model is None:
        model = os.getenv(
            'ORCH_ANTIGRAVITY_MODEL',
            'gemini-4-argon-medium'
        )

    argv = [
        'agy',
        '--print',
        prompt,
        '--model',
        model,
        '--mode',
        mode,
        '--output-format',
        'json'
    ]

    raw = run_command(argv, cwd, timeout)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            'Antigravity returned invalid CLI JSON'
        ) from exc

    if result.get('status') != 'SUCCESS':
        raise RuntimeError(
            f'Antigravity failed: {result.get("status")}'
        )

    denied_actions = result.get('denied_actions') or []

    if denied_actions:
        raise RuntimeError(
            'Antigravity denied requiredactions: '
            + json.dumps(denied_actions, ensure_ascii=False)
        )
    response = result.get('response')

    if not isinstance(response, str) or not response.strip():
        raise RuntimeError(
            'Antigravity returned an empty or invalid response'
        )

    return response


def coding_agent(prompt: str, cwd: str, role: str, state: State | None = None) -> str:
    """Seleciona o agente responsável pelo planejamento ou implementação."""
    if role not in ('planner', 'implementer'):
        raise ValueError(f'Invalid agent role: {role}')

    provider = os.getenv(f'ORCH_{role.upper()}', 'claude').lower()

    if provider == 'claude':
        try:
            return claude(
                prompt,
                cwd,
                int(os.getenv('AGENT_TIMEOUT', '900'))
            )
        except RuntimeError as exc:
            message = str(exc).lower()

            quota_errors = (
                'rate limit',
                'rate_limit',
                'usage limit',
                'usage_limit',
                'quota exceeded',
                'out of extra usage',
                'hit your limit',
                'you have reached your limit',
            )

            if role != 'planner' or not any(
                marker in message for marker in quota_errors
            ):
                raise

            if state is not None:
                event(state, 'agent_fallback', {
                    'role': role,
                    'primary': 'claude',
                    'fallback': 'antigravity',
                    'reason': 'usage_limit',
                })

            print(
                '[orchestrator] Claude usage limit detected. '
                'Falling back to Antigravity.',
                flush=True
            )

            return antigravity(
                prompt,
                cwd,
                timeout=int(os.getenv('AGENT_TIMEOUT', '900')),
                mode='plan',
                model=os.getenv(
                    'ORCH_PLANNER_MODEL',
                    'gemini-4-argon-medium'
                )
            )

    if provider == 'antigravity':
        mode = 'plan' if role == 'planner' else 'accept-edits'
        model = os.getenv(
            f'ORCH_{role.upper()}_MODEL',
            'gemini-4-argon-medium'
        )

        return antigravity(
            prompt,
            cwd,
            timeout=int(os.getenv('AGENT_TIMEOUT', '900')),
            mode=mode,
            model=model
        )

    raise ValueError(f'Unsupported agent provider: {provider}')


def plan(state: State) -> State:
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
    result = coding_agent(prompt, state['worktree'], 'implementer')
    event(state, 'implementation', {
        'task': task['id'], 'attempt': attempts + 1, 'output': result[-6000:],
    })
    return {'attempts': attempts + 1}


def review(state: State) -> State:
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
    result = extract_json(codex(
        prompt, worktree, int(os.getenv('AGENT_TIMEOUT', '900')),
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
    repo_path = Path(repo).resolve()
    scope = Path(scope_file).resolve().read_text(encoding='utf-8')
    if len(scope) > 100_000:
        raise ValueError('Scope exceeds 100k characters')
    run_id = 'run-' + uuid.uuid4().hex[:12]
    worktree = prepare(repo_path, run_id)
    state: State = {
        'run_id': run_id, 'repo': str(repo_path),
        'worktree': str(worktree), 'scope': scope,
    }
    event(state, 'started', {
        'repo': str(repo_path), 'worktree': str(worktree),
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
    }
    if dry_run:
        return {**state, 'entry_point': entry_point}

    event(state, 'resumed', {
        'task_index': task_index, 'task': tasks[task_index]['id'],
        'attempts': attempts, 'entry_point': entry_point,
    })
    return _invoke(state, entry_point)
