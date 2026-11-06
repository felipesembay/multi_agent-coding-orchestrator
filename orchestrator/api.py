"""Local API for project management and orchestration observability."""
import os
from contextlib import closing
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI, HTTPException, Query
from starlette.responses import JSONResponse

from .project_api import router as project_router
from .projects import ProjectError
from .local_security import protect_project_routes

from .core import db, db_path
from .dashboard import summarize
from .execution_manager import all_summaries, get_managed, consolidated

app = FastAPI(title='Multi-Agent Orchestrator — local project platform')
app.middleware('http')(protect_project_routes)
app.include_router(project_router)


@app.exception_handler(ProjectError)
async def project_error_handler(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=exc.status)


@app.get('/health')
def health():
    with closing(db(db_path())) as conn:
        conn.execute('SELECT 1 FROM events LIMIT 1')
    return {'status': 'ok'}


@app.get('/runs')
def runs(
    paginated: bool = False,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str = Query('', max_length=200),
    status: str = Query('', max_length=100),
    order: str = Query('desc', pattern='^(asc|desc)$'),
):
    with closing(db(db_path())) as conn:
        rows = [summary for summary, _ in all_summaries(conn)]
    rows = [r for r in rows if search.lower() in r['run_id'].lower() and (not status or r['status'] == status)]
    rows.sort(key=lambda r: (r['last_event'] or '', r['run_id']), reverse=order == 'desc')
    items = rows[offset:offset + limit]
    # Preserve the original array response and last_event field for existing clients.
    return {'items': items, 'total': len(rows), 'limit': limit, 'offset': offset} if paginated else items


@app.get('/overview')
def overview():
    with closing(db(db_path())) as conn:
        rows = all_summaries(conn)
    counts = {}
    durations = []
    activity = []
    for summary, events in rows:
        status = summary['status']
        counts[status] = counts.get(status, 0) + 1
        if summary['duration_seconds'] is not None:
            durations.append(summary['duration_seconds'])
        activity.extend(dict(run_id=summary['run_id'], **event) for event in events)
    activity.sort(key=lambda e: e['id'], reverse=True)
    return dict(total=len(rows), counts=counts,
                average_duration_seconds=sum(durations) / len(durations) if durations else None,
                duration_sample_count=len(durations), activity=activity[:8])


@app.get('/settings')
def settings():
    def component(name):
        try:
            return version(name)
        except PackageNotFoundError:
            return None
    # Explicit allowlist: never serialize os.environ or credentials.
    return dict(planner=os.getenv('ORCH_PLANNER', 'claude'),
                implementer=os.getenv('ORCH_IMPLEMENTER', 'claude'),
                reviewer='codex',
                planner_model=os.getenv('ORCH_PLANNER_MODEL') if os.getenv('ORCH_PLANNER', 'claude').lower() == 'antigravity' else None,
                implementer_model=os.getenv('ORCH_IMPLEMENTER_MODEL') if os.getenv('ORCH_IMPLEMENTER', 'claude').lower() == 'antigravity' else None,
                antigravity_default_model=os.getenv('ORCH_ANTIGRAVITY_MODEL', 'gemini-4-argon-medium'),
                test_command=os.getenv('ORCH_TEST_COMMAND') or None,
                database=db_path(),
                versions={name: component(name) for name in ('fastapi', 'langgraph', 'pydantic')})


@app.get('/runs/{run_id}/events')
def events(run_id: str):
    with closing(db(db_path())) as conn:
        return [dict(id=r[0], at=r[1], stage=r[2], payload=r[3]) for r in conn.execute(
            'SELECT id,at,stage,payload FROM events WHERE run_id=? ORDER BY id', (run_id,))]


@app.get('/runs/{run_id}')
def run_detail(run_id: str):
    history = events(run_id)
    managed = get_managed(run_id)
    if managed:
        return dict(**consolidated(managed, history), events=history)
    if not history:
        raise HTTPException(status_code=404, detail='Execução não encontrada')
    return dict(**summarize(run_id, history), events=history)
