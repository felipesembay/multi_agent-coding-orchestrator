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


WORKFLOW_MIGRATION = [
    """CREATE TABLE workflow_definitions (
        id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        is_preset INTEGER NOT NULL DEFAULT 0 CHECK(is_preset IN (0,1)),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, archived_at TEXT)""",
    """CREATE TABLE workflow_versions (
        id TEXT PRIMARY KEY NOT NULL,
        definition_id TEXT NOT NULL REFERENCES workflow_definitions(id),
        version INTEGER NOT NULL CHECK(typeof(version)='integer' AND version>=1),
        schema_version INTEGER NOT NULL CHECK(typeof(schema_version)='integer' AND schema_version>=1),
        body TEXT NOT NULL CHECK(CASE WHEN json_valid(body) THEN json_type(body)='object' ELSE 0 END),
        digest TEXT NOT NULL CHECK(length(digest)=64 AND digest NOT GLOB '*[^0-9a-f]*'),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(definition_id,version))""",
    """CREATE TRIGGER workflow_versions_no_update BEFORE UPDATE ON workflow_versions
        BEGIN SELECT RAISE(ABORT, 'Workflow versions are immutable'); END""",
    """CREATE TRIGGER workflow_versions_no_delete BEFORE DELETE ON workflow_versions
        BEGIN SELECT RAISE(ABORT, 'Workflow versions are immutable'); END""",
    # REPLACE can delete conflicts without firing DELETE triggers when recursive
    # triggers are disabled (SQLite's default). Refuse replacement before it runs.
    """CREATE TRIGGER workflow_versions_no_replace BEFORE INSERT ON workflow_versions
        WHEN EXISTS(SELECT 1 FROM workflow_versions WHERE id=NEW.id
                    OR (definition_id=NEW.definition_id AND version=NEW.version))
        BEGIN SELECT RAISE(ABORT, 'Workflow versions are immutable'); END""",
    """CREATE TABLE provider_configs (
        id TEXT PRIMARY KEY NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('agent_runtime','model_provider')),
        adapter TEXT NOT NULL, display_name TEXT NOT NULL,
        settings TEXT NOT NULL DEFAULT '{}'
            CHECK(CASE WHEN json_valid(settings) THEN json_type(settings)='object' ELSE 0 END),
        credential_ref TEXT,
        enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)))""",
    'ALTER TABLE managed_runs ADD COLUMN workflow_version_id TEXT REFERENCES workflow_versions(id)',
    """ALTER TABLE managed_runs ADD COLUMN bindings TEXT
        CHECK(bindings IS NULL OR CASE WHEN json_valid(bindings) THEN json_type(bindings)='object' ELSE 0 END)""",
    """ALTER TABLE managed_runs ADD COLUMN workflow_digest TEXT
        CHECK(workflow_digest IS NULL OR (length(workflow_digest)=64 AND workflow_digest NOT GLOB '*[^0-9a-f]*'))""",
    'CREATE INDEX runs_by_workflow_version ON managed_runs(workflow_version_id)',
    'INSERT INTO platform_migrations(version) VALUES(4)',
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
        if not conn.execute('SELECT 1 FROM platform_migrations WHERE version=3').fetchone():
            conn.execute('BEGIN IMMEDIATE')
            # Recheck after acquiring the writer lock: another connection may have migrated.
            if not conn.execute('SELECT 1 FROM platform_migrations WHERE version=3').fetchone():
                conn.execute('ALTER TABLE projects ADD COLUMN deleted_at TEXT')
                conn.execute('INSERT INTO platform_migrations(version) VALUES(3)')
            conn.commit()
        if not conn.execute('SELECT 1 FROM platform_migrations WHERE version=4').fetchone():
            conn.execute('BEGIN IMMEDIATE')
            # The pre-lock read is only a fast path. A competing opener may have
            # committed the complete migration while this connection waited.
            if not conn.execute('SELECT 1 FROM platform_migrations WHERE version=4').fetchone():
                for statement in WORKFLOW_MIGRATION:
                    conn.execute(statement)
            conn.commit()
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
