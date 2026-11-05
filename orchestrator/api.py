import os
from pathlib import Path
from fastapi import FastAPI
from .core import db

app=FastAPI(title='Multi-Agent Orchestrator — local read-only dashboard API')
@app.get('/health')
def health():return {'status':'ok'}
@app.get('/runs')
def runs():
    with db(os.environ.get('ORCH_DB',str(Path.home()/'.local/state/multi-agent-orchestrator/events.db'))) as c:
        return [{'run_id':r[0],'last_event':r[1]} for r in c.execute('SELECT run_id,MAX(at) FROM events GROUP BY run_id ORDER BY MAX(at) DESC LIMIT 50')]
@app.get('/runs/{run_id}/events')
def events(run_id:str):
    with db(os.environ.get('ORCH_DB',str(Path.home()/'.local/state/multi-agent-orchestrator/events.db'))) as c:
        return [{'at':r[0],'stage':r[1],'payload':r[2]} for r in c.execute('SELECT at,stage,payload FROM events WHERE run_id=? ORDER BY id',(run_id,))]
