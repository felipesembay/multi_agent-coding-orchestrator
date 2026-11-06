"""Persistent FIFO worker. Run separately: python -m orchestrator.worker.

API restarts do not stop it. Worker restarts reconcile old process groups, never
replay agent calls. Interrupted work requires inspection and an explicit new run.
"""
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .core import db_path
from .execution_manager import boot_id, process_identity, same_process
from .project_store import connection
from .projects import audit


def group_members(group):
    members = []
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            info = process_identity(int(path.name))
            if info and info['group'] == group and info['state'] != 'Z':
                members.append(int(path.name))
    return members


def verified_group(row):
    if row['boot_id'] != boot_id() or not row['pid']:
        return False
    current = process_identity(row['pid'])
    if same_process(row['pid'], row['process_start'], row['boot_id']) and current['session'] == row['pid'] and current['group'] == row['pid']:
        return True
    expected = ('ORCH_DISPATCH_TOKEN=' + row['dispatch_token']).encode()
    for pid in group_members(row['pid']):
        try:
            if expected in Path(f'/proc/{pid}/environ').read_bytes().split(b'\x00'):
                return True
        except OSError:
            pass
    return False


def clean_group(row):
    """Never signal a reused PID/group without identity or dispatch-token proof."""
    if not row['pid'] or row['boot_id'] != boot_id():
        return True
    members = group_members(row['pid'])
    if not members:
        return True
    if not verified_group(row):
        return False
    try:
        os.killpg(row['pid'], signal.SIGKILL)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    for _ in range(20):
        if not group_members(row['pid']):
            return True
        time.sleep(.05)
    return False


def reconcile():
    with connection() as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM managed_runs WHERE status='running' OR orphaned=1")]
    for row in rows:
        cleaned = clean_group(row)
        with connection() as conn:
            conn.execute("UPDATE managed_runs SET status='interrupted',orphaned=?,finished_at=COALESCE(finished_at,CURRENT_TIMESTAMP),error=? WHERE run_id=?", (0 if cleaned else 1, 'Execução interrompida. Inspecione a worktree antes de iniciar outra execução.' if cleaned else 'Processo órfão sem identificação suficiente. Repositório permanece reservado para inspeção manual.', row['run_id']))
            audit(conn, 'execution.reconciled', row['project_id'], run_id=row['run_id'], orphaned=not cleaned)
            conn.commit()


class Worker:
    def __init__(self):
        self.id = uuid.uuid4().hex
        self.stop = False
        self.pid = os.getpid()
        self.start = process_identity(self.pid)['start']
        self.boot = boot_id()

    def heartbeat(self):
        with connection() as conn:
            conn.execute('''INSERT INTO execution_worker VALUES(1,?,?,?,?,?)
                ON CONFLICT(singleton) DO UPDATE SET worker_id=excluded.worker_id,pid=excluded.pid,
                process_start=excluded.process_start,boot_id=excluded.boot_id,heartbeat=excluded.heartbeat''',
                         (self.id, self.pid, self.start, self.boot, time.time()))
            conn.commit()

    def claim(self):
        with connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute("SELECT * FROM managed_runs WHERE status='queued' ORDER BY rowid LIMIT 1").fetchone()
            if not row:
                return None
            conn.execute("UPDATE managed_runs SET status='running',started_at=CURRENT_TIMESTAMP,heartbeat=?,worker_id=? WHERE run_id=?", (time.time(), self.id, row['run_id']))
            audit(conn, 'execution.dispatched', row['project_id'], run_id=row['run_id'])
            conn.commit()
            return dict(row)

    def spawn(self, row):
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update(ORCH_DB=str(Path(db_path()).expanduser().resolve()),
                   ORCH_DISPATCH_TOKEN=row['dispatch_token'], ORCH_WORKER_ID=self.id,
                   GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        return subprocess.Popen(
            [sys.executable, '-m', 'orchestrator.execution_runner', '--run-id', row['run_id']],
            cwd=str(Path(__file__).resolve().parent.parent), env=env,
            start_new_session=True, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def run_once(self):
        self.heartbeat()
        row = self.claim()
        if row is None:
            return False
        child = None
        try:
            child = self.spawn(row)
            info = process_identity(child.pid)
            if info is None:
                raise RuntimeError('Processo encerrou antes da inicialização.')
            with connection() as conn:
                conn.execute('UPDATE managed_runs SET pid=?,process_start=?,boot_id=? WHERE run_id=?',
                             (child.pid, info['start'], self.boot, row['run_id']))
                conn.commit()
            while child.poll() is None and not self.stop:
                self.heartbeat()
                with connection() as conn:
                    conn.execute('UPDATE managed_runs SET heartbeat=? WHERE run_id=?', (time.time(), row['run_id']))
                    conn.commit()
                time.sleep(.25)
            with connection() as conn:
                current = dict(conn.execute('SELECT * FROM managed_runs WHERE run_id=?', (row['run_id'],)).fetchone())
            cleaned = clean_group(current)
            if child.poll() is None and cleaned:
                child.wait(timeout=5)
            result = json.loads(current['result']) if current['result'] else {}
            status = result.get('status')
            if self.stop or not cleaned or (child.returncode is not None and child.returncode < 0):
                status = 'interrupted'
            elif status not in ('ready_for_human_review', 'blocked', 'failed'):
                status = 'failed'
            error = current['error'] or (None if status in ('ready_for_human_review', 'blocked') else 'O processo encerrou sem concluir o workflow. Inspecione os eventos e a worktree.')
            with connection() as conn:
                conn.execute('UPDATE managed_runs SET status=?,finished_at=CURRENT_TIMESTAMP,orphaned=?,error=? WHERE run_id=?', (status, 0 if cleaned else 1, error, row['run_id']))
                audit(conn, 'execution.finished', row['project_id'], run_id=row['run_id'], status=status)
                conn.commit()
        except Exception:
            # Do not free a repository while an unverified child may still be alive.
            with connection() as conn:
                current = dict(conn.execute('SELECT * FROM managed_runs WHERE run_id=?', (row['run_id'],)).fetchone())
            cleaned = clean_group(current)
            if child is not None and cleaned and current['pid'] is not None:
                child.wait(timeout=5)
            if child is not None and current['pid'] is None:
                # No handshake was persisted, so this child cannot have invoked agents.
                child.kill()
                child.wait(timeout=5)
            with connection() as conn:
                conn.execute("UPDATE managed_runs SET status='failed',finished_at=CURRENT_TIMESTAMP,orphaned=?,error=? WHERE run_id=?", (0 if cleaned else 1, 'Falha ao iniciar ou supervisionar o processo de execução. Verifique o worker.', row['run_id']))
                audit(conn, 'execution.process_failed', row['project_id'], run_id=row['run_id'])
                conn.commit()
        return True

    def run(self):
        path = Path(db_path()).expanduser().resolve().with_suffix('.worker.lock')
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise SystemExit('Já existe um worker para este banco.')
        def stop(signum, frame):
            self.stop = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        try:
            reconcile()
            self.heartbeat()
            print('Execution worker pronto. Aguardando solicitações persistidas.', flush=True)
            while not self.stop:
                if not self.run_once():
                    # Re-check unresolved orphans before accepting another repository reservation.
                    with connection() as conn:
                        orphaned = conn.execute('SELECT 1 FROM managed_runs WHERE orphaned=1 LIMIT 1').fetchone()
                    if orphaned:
                        reconcile()
                    time.sleep(.5)
        finally:
            with connection() as conn:
                conn.execute('DELETE FROM execution_worker WHERE worker_id=?', (self.id,))
                conn.commit()
            os.close(fd)


if __name__ == '__main__':
    Worker().run()
