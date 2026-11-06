"""Versioned project persistence, separate from the orchestration event protocol."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .core import db_path

MIGRATION = [
    '''CREATE TABLE IF NOT EXISTS platform_migrations (version INTEGER PRIMARY KEY)''',
    '''CREATE TABLE IF NOT EXISTS repositories (
        id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, git_common_dir TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''',
    '''CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
        objectives TEXT NOT NULL, repository_id TEXT NOT NULL REFERENCES repositories(id),
        state TEXT NOT NULL DEFAULT 'active' CHECK(state IN ('active','archived')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''',
    '''CREATE TABLE IF NOT EXISTS project_requests (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        title TEXT NOT NULL, content TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'submitted',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''',
    '''CREATE INDEX IF NOT EXISTS requests_by_project ON project_requests(project_id, created_at)''',
    '''CREATE TABLE IF NOT EXISTS project_previews (
        token TEXT PRIMARY KEY, payload TEXT NOT NULL, parent_device INTEGER NOT NULL,
        parent_inode INTEGER NOT NULL, expires_at REAL NOT NULL,
        project_id TEXT REFERENCES projects(id))''',
    '''CREATE TABLE IF NOT EXISTS platform_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        action TEXT NOT NULL, project_id TEXT, details TEXT NOT NULL)''',
    '''INSERT OR IGNORE INTO platform_migrations(version) VALUES(1)''',
]


EXECUTION_MIGRATION = [
    """CREATE TABLE IF NOT EXISTS managed_runs (
        run_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        request_id TEXT NOT NULL REFERENCES project_requests(id),
        request_title TEXT NOT NULL, scope TEXT NOT NULL, repo TEXT NOT NULL,
        repo_identity TEXT NOT NULL, config TEXT NOT NULL,
        idempotency_key TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL CHECK(status IN ('queued','running','ready_for_human_review','blocked','failed','interrupted')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        started_at TEXT, finished_at TEXT, heartbeat REAL,
        worktree TEXT, error TEXT, result TEXT,
        pid INTEGER, process_start TEXT, boot_id TEXT, worker_id TEXT,
        dispatch_token TEXT NOT NULL, orphaned INTEGER NOT NULL DEFAULT 0)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS one_active_run_per_repository
        ON managed_runs(repo_identity) WHERE status IN ('queued','running') OR orphaned=1""",
    """CREATE INDEX IF NOT EXISTS runs_by_project ON managed_runs(project_id,created_at)""",
    """CREATE TABLE IF NOT EXISTS execution_worker (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), worker_id TEXT NOT NULL,
        pid INTEGER NOT NULL, process_start TEXT NOT NULL, boot_id TEXT NOT NULL,
        heartbeat REAL NOT NULL)""",
    "INSERT OR IGNORE INTO platform_migrations(version) VALUES(2)",
]


@contextmanager
def connection():
    path = Path(db_path()).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name='platform_migrations'").fetchone()
        if not exists or not conn.execute('SELECT 1 FROM platform_migrations WHERE version=1').fetchone():
            conn.execute('BEGIN IMMEDIATE')
            for statement in MIGRATION:
                conn.execute(statement)
            conn.commit()
        if not conn.execute('SELECT 1 FROM platform_migrations WHERE version=2').fetchone():
            conn.execute('BEGIN IMMEDIATE')
            for statement in EXECUTION_MIGRATION:
                conn.execute(statement)
            conn.commit()
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
