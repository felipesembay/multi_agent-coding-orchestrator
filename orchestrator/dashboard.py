"""Read models for the dashboard. Does not invoke agents or inspect worktrees."""
import json
from datetime import datetime, timezone


def object_payload(raw):
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (ValueError, TypeError, AttributeError):
        return None


def summarize(run_id, events):
    result = dict(run_id=run_id, repo=None, worktree=None, status='unknown',
                  started_at=None, finished_at=None, last_event=None,
                  duration_seconds=None, task_count=None, tests_passed=None,
                  current_stage=None, attempts=0)
    for event in events:
        stage, at = event['stage'], event['at']
        p = object_payload(event['payload'])
        result.update(last_event=at, current_stage=p.get('stage') if stage == 'stage_started' and p.get('stage') in ('plan', 'implementation', 'review') else stage)
        if stage == 'started':
            result.update(repo=p.get('repo') if isinstance(p.get('repo'), str) else None,
                          worktree=p.get('worktree') if isinstance(p.get('worktree'), str) else None,
                          started_at=at, status='running', finished_at=None)
        elif stage == 'plan':
            if isinstance(p.get('tasks'), list):
                result['task_count'] = len(p['tasks'])
        elif stage == 'implementation':
            result['attempts'] += 1
        elif stage == 'review':
            test = p.get('test_result')
            result['tests_passed'] = test.get('passed') if isinstance(test, dict) and isinstance(test.get('passed'), bool) else None
        elif stage == 'resumed':
            result.update(status='running', finished_at=None)
        elif stage == 'finished':
            # A finished event is not proof of success or human approval.
            status = p.get('status')
            result.update(status=status if isinstance(status, str) and status else 'unknown', finished_at=at)
            if isinstance(p.get('worktree'), str):
                result['worktree'] = p['worktree']
        elif stage in ('blocked', 'error'):
            result.update(status=stage, finished_at=at)
    start, end = timestamp(result['started_at']), timestamp(result['finished_at'])
    if start is not None and end is not None and end >= start:
        result['duration_seconds'] = end - start
    return result


def read_runs(conn):
    grouped = {}
    for run_id, event_id, at, stage, payload in conn.execute(
        'SELECT run_id,id,at,stage,payload FROM events ORDER BY id'
    ):
        grouped.setdefault(run_id, []).append(dict(id=event_id, at=at, stage=stage, payload=payload))
    return [(summarize(run_id, events), events) for run_id, events in grouped.items()]
