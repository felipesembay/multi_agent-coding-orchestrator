"""Durable submission/read models. HTTP never invokes the workflow or spawns agents."""
import hashlib
import json
import os
import shlex
import shutil
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from . import projects
from .core import db, db_path
from .dashboard import summarize
from .project_store import connection
from .repository_lock import identity, repository_lock

ACTIVE = ('queued', 'running')
TERMINAL = ('ready_for_human_review', 'blocked', 'failed', 'interrupted')
DEFAULT_TEST_COMMANDS = [
    ['python', '-m', 'pytest', '-q'], ['python3', '-m', 'pytest', '-q'],
    ['pytest', '-q'], ['npm', 'test'], ['npm', 'test', '--', '--run'],
    ['npm', 'run', 'test', '--', '--run'],
]


class StartInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmed: Literal[True]
    configuration_digest: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=16, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')


class StartResponse(BaseModel):
    run_id: str
    status: Literal['queued', 'running', 'ready_for_human_review', 'blocked', 'failed', 'interrupted']
    project_id: str
    request_id: str


class ExecutionConfiguration(BaseModel):
    planner: str
    implementer: str
    reviewer: str
    planner_model: Optional[str]
    implementer_model: Optional[str]
    planner_fallback_model: str
    test_command: str
    max_attempts: int
    agent_timeout: int
    test_timeout: int
    worktree_base: str


class WorkerStatus(BaseModel):
    online: bool
    heartbeat: Optional[float]


class PreflightResponse(BaseModel):
    configuration: ExecutionConfiguration
    configuration_digest: str
    worker: WorkerStatus
    ready: bool
    errors: list[str]


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def process_identity(pid):
    try:
        raw = Path(f'/proc/{pid}/stat').read_text()
        fields = raw[raw.rfind(')') + 2:].split()
        return dict(state=fields[0], group=int(fields[2]), session=int(fields[3]), start=fields[19])
    except (OSError, ValueError, IndexError):
        return None


def same_process(pid, start, boot):
    if not pid or boot != boot_id():
        return False
    current = process_identity(pid)
    return current is not None and current['start'] == start and current['state'] != 'Z'


def worker_status():
    with connection() as conn:
        row = conn.execute('SELECT * FROM execution_worker WHERE singleton=1').fetchone()
    online = bool(row and time.time() - row['heartbeat'] < 12 and same_process(row['pid'], row['process_start'], row['boot_id']))
    return dict(online=online, heartbeat=row['heartbeat'] if row else None)


def validate_test_command(command):
    try:
        argv = shlex.split(command)
        configured = os.getenv('ORCH_ALLOWED_TEST_COMMANDS')
        allowed = json.loads(configured) if configured else DEFAULT_TEST_COMMANDS
    except (ValueError, TypeError) as exc:
        raise projects.ProjectError('Configuração inválida da allowlist de testes.', 422) from exc
    if not isinstance(allowed, list) or not all(isinstance(a, list) and a and all(isinstance(v, str) for v in a) for a in allowed):
        raise projects.ProjectError('ORCH_ALLOWED_TEST_COMMANDS deve ser um JSON de listas de argumentos.', 422)
    if not argv:
        raise projects.ProjectError('Configure ORCH_TEST_COMMAND no processo da API antes de iniciar.', 422)
    if argv not in allowed:
        raise projects.ProjectError('O comando de testes configurado não está na allowlist do servidor.', 422)
    if any(value in (';', '&&', '||', '|', '>', '<') for value in argv) or Path(argv[0]).name in ('sh', 'bash', 'zsh', 'fish', 'cmd', 'powershell'):
        raise projects.ProjectError('Comandos de shell não são permitidos como perfil de testes.', 422)
    if '/' in argv[0] and not Path(argv[0]).is_absolute():
        raise projects.ProjectError('Use um executável de testes no PATH ou um caminho absoluto autorizado.', 422)
    if not shutil.which(argv[0]):
        raise projects.ProjectError('Executável do comando de testes não encontrado no servidor.', 422)
    return argv


def configuration(project):
    try:
        config = ExecutionConfiguration(
            planner=os.getenv('ORCH_PLANNER', 'claude').lower(),
            implementer=os.getenv('ORCH_IMPLEMENTER', 'claude').lower(), reviewer='codex',
            planner_model=os.getenv('ORCH_PLANNER_MODEL', 'gemini-4-argon-medium') if os.getenv('ORCH_PLANNER', 'claude').lower() == 'antigravity' else None,
            implementer_model=os.getenv('ORCH_IMPLEMENTER_MODEL', 'gemini-4-argon-medium') if os.getenv('ORCH_IMPLEMENTER', 'claude').lower() == 'antigravity' else None,
            planner_fallback_model=os.getenv('ORCH_PLANNER_MODEL', 'gemini-4-argon-medium'),
            test_command=os.getenv('ORCH_TEST_COMMAND', '').strip(),
            max_attempts=int(os.getenv('MAX_ATTEMPTS', '3')),
            agent_timeout=int(os.getenv('AGENT_TIMEOUT', '900')),
            test_timeout=int(os.getenv('TEST_TIMEOUT', '300')),
            worktree_base=str(Path(os.getenv('ORCH_WORKTREES', str(Path(project['repo_path']).parent / (Path(project['repo_path']).name + '-agent-worktrees')))).expanduser().resolve()),
        ).model_dump()
    except ValueError as exc:
        raise projects.ProjectError('Configuração de execução inválida no servidor.', 422) from exc
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    return config, digest


def validate_configuration(config):
    for role in ('planner', 'implementer'):
        if config[role] not in ('claude', 'antigravity'):
            raise projects.ProjectError(f'Provider não suportado para {role}.', 422)
    tools = {'git', 'codex'} | {'agy' if config[role] == 'antigravity' else 'claude' for role in ('planner', 'implementer')}
    missing = sorted(tool for tool in tools if not shutil.which(tool))
    if missing:
        raise projects.ProjectError('Ferramentas locais ausentes: ' + ', '.join(missing), 422)
    validate_test_command(config['test_command'])
    if not (1 <= config['max_attempts'] <= 20 and 1 <= config['agent_timeout'] <= 86400 and 1 <= config['test_timeout'] <= 86400):
        raise projects.ProjectError('Tentativas e timeouts configurados fora dos limites.', 422)
    projects.authorized_path(config['worktree_base'], allow_root=True)


def validate_repository(project):
    data = projects.ProjectInput(name=project['name'], repo_path=project['repo_path'], mode='existing')
    path, _ = projects.validate_input(data)
    projects.git(path, 'rev-parse', '--verify', 'HEAD')
    if projects.git(path, 'status', '--porcelain'):
        raise projects.ProjectError('O repositório contém alterações locais. Faça commit ou stash antes de executar.', 409)
    common = identity(path)
    try:
        with repository_lock(path):
            pass
    except RuntimeError as exc:
        raise projects.ProjectError(str(exc), 409) from exc
    return common


def preflight(project_id):
    project = projects.get_project(project_id)
    config, digest = configuration(project)
    errors = []
    for check in (lambda: validate_configuration(config), lambda: validate_repository(project)):
        try:
            check()
        except (projects.ProjectError, OSError, ValueError) as exc:
            errors.append(str(exc))
    worker = worker_status()
    if not worker['online']:
        errors.append('Worker offline. Inicie python -m orchestrator.worker com o mesmo ORCH_DB da API.')
    if project['state'] != 'active':
        errors.append('Reative o projeto antes de iniciar uma execução.')
    with connection() as conn:
        busy = conn.execute("SELECT run_id FROM managed_runs WHERE repo_identity=(SELECT git_common_dir FROM repositories WHERE id=?) AND (status IN ('queued','running') OR orphaned=1)", (project['repository_id'],)).fetchone()
    if busy:
        errors.append('Este repositório já possui uma execução ativa ou um processo órfão pendente.')
    return dict(configuration=config, configuration_digest=digest, worker=worker, ready=not errors, errors=errors)


def submit(project_id, request_id, data):
    with connection() as conn:
        previous = conn.execute('SELECT * FROM managed_runs WHERE idempotency_key=?', (data.idempotency_key,)).fetchone()
        if previous:
            if previous['project_id'] != project_id or previous['request_id'] != request_id:
                raise projects.ProjectError('Chave de idempotência já utilizada para outra solicitação.', 409)
            return {key: previous[key] for key in ('run_id', 'status', 'project_id', 'request_id')}
        project = projects.get_project(project_id, conn)
        request = conn.execute('SELECT * FROM project_requests WHERE id=?', (request_id,)).fetchone()
    if request is None:
        raise projects.ProjectError('Solicitação não encontrada.', 404)
    if request['project_id'] != project_id:
        raise projects.ProjectError('A solicitação não pertence a este projeto.', 409)
    if project['state'] != 'active':
        raise projects.ProjectError('Reative o projeto antes de executar.', 409)
    config, digest = configuration(project)
    if data.configuration_digest != digest:
        raise projects.ProjectError('A configuração mudou. Revise a confirmação novamente.', 409)
    validate_configuration(config)
    common = validate_repository(project)
    if not worker_status()['online']:
        raise projects.ProjectError('Worker offline. Inicie python -m orchestrator.worker com o mesmo ORCH_DB.', 503)
    scope = request['content']  # Exact saved requirement; no user-created Markdown file.
    run_id = 'run-' + uuid.uuid4().hex[:12]
    try:
        with connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            # Re-read mutable entities and idempotency inside the reservation transaction.
            previous = conn.execute('SELECT * FROM managed_runs WHERE idempotency_key=?', (data.idempotency_key,)).fetchone()
            if previous:
                if previous['project_id'] != project_id or previous['request_id'] != request_id:
                    raise projects.ProjectError('Chave de idempotência já utilizada.', 409)
                return {key: previous[key] for key in ('run_id', 'status', 'project_id', 'request_id')}
            if projects.get_project(project_id, conn)['state'] != 'active':
                raise projects.ProjectError('Projeto arquivado durante a confirmação.', 409)
            conn.execute('''INSERT INTO managed_runs(run_id,project_id,request_id,request_title,scope,repo,repo_identity,config,idempotency_key,status,dispatch_token)
                            VALUES(?,?,?,?,?,?,?,?,?,'queued',?)''',
                         (run_id, project_id, request_id, request['title'], scope, project['repo_path'], common, json.dumps(config), data.idempotency_key, uuid.uuid4().hex))
            projects.audit(conn, 'execution.queued', project_id, run_id=run_id, request_id=request_id)
            conn.commit()
    except sqlite3.IntegrityError as exc:
        raise projects.ProjectError('Já existe uma execução ativa ou um processo órfão neste repositório.', 409) from exc
    return dict(run_id=run_id, status='queued', project_id=project_id, request_id=request_id)


def get_managed(run_id):
    with connection() as conn:
        row = conn.execute('''SELECT m.*, p.name AS project_name FROM managed_runs m
                              JOIN projects p ON p.id=m.project_id WHERE run_id=?''', (run_id,)).fetchone()
        return dict(row) if row else None


def consolidated(row, events):
    summary = summarize(row['run_id'], events)
    summary.update(repo=row['repo'], status=row['status'], worktree=row['worktree'] or summary['worktree'],
                   started_at=row['started_at'], finished_at=row['finished_at'])
    if row['started_at'] and row['finished_at']:
        from .dashboard import timestamp
        summary['duration_seconds'] = max(0, timestamp(row['finished_at']) - timestamp(row['started_at']))
    summary.update(project_id=row['project_id'], project_name=row['project_name'], request_id=row['request_id'],
                   request_title=row['request_title'], created_at=row['created_at'], error=row['error'],
                   configuration=json.loads(row['config']), manager_status=row['status'], orphaned=bool(row['orphaned']))
    summary['supervisor_online'] = worker_status()['online'] if row['status'] in ACTIVE else None
    if not summary['last_event']:
        summary['last_event'] = row['finished_at'] or row['started_at'] or row['created_at']
    return summary


def all_summaries(conn):
    """Merge lifecycle records with existing event summaries without duplicating runs."""
    from .dashboard import read_runs
    legacy = {summary['run_id']: (summary, events) for summary, events in read_runs(conn)}
    with connection() as owned:
        rows = owned.execute('SELECT m.*,p.name AS project_name FROM managed_runs m JOIN projects p ON p.id=m.project_id').fetchall()
    for row in rows:
        events = legacy.get(row['run_id'], ({}, []))[1]
        legacy[row['run_id']] = (consolidated(dict(row), events), events)
    return list(legacy.values())


def project_runs(project_id, legacy=False):
    project = projects.get_project(project_id)
    with closing(db(db_path())) as conn:
        rows = all_summaries(conn)
    runs = [summary for summary, _ in rows if summary.get('project_id') == project_id or (legacy and not summary.get('project_id') and summary['repo'] == project['repo_path'])]
    return sorted(runs, key=lambda item: item['last_event'] or '', reverse=True)
