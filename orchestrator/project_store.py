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


ACCOUNTING_MIGRATION = [
    """CREATE TABLE step_executions (
        id TEXT PRIMARY KEY NOT NULL,
        run_id TEXT NOT NULL,
        node TEXT NOT NULL,
        task_id TEXT,
        attempt INTEGER NOT NULL CHECK(typeof(attempt)='integer' AND attempt>=1),
        role TEXT,
        idempotency_key TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL CHECK(status IN ('started','completed','failed','needs_inspection','skipped')),
        side_effects TEXT NOT NULL DEFAULT 'none' CHECK(side_effects IN ('none','worktree_write','exec')),
        git_head_before TEXT,
        tree_digest_before TEXT,
        tree_digest_after TEXT,
        started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        finished_at TEXT,
        error TEXT)""",
    'CREATE INDEX step_executions_by_run ON step_executions(run_id, started_at)',
    """CREATE TABLE price_catalog_versions (
        id TEXT PRIMARY KEY NOT NULL,
        source TEXT NOT NULL,
        fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        notes TEXT NOT NULL DEFAULT '')""",
    """CREATE TABLE price_entries (
        id TEXT PRIMARY KEY NOT NULL,
        catalog_version_id TEXT NOT NULL REFERENCES price_catalog_versions(id),
        adapter TEXT NOT NULL,
        model TEXT NOT NULL,
        unit TEXT NOT NULL DEFAULT 'per_1m_tokens' CHECK(unit IN ('per_1m_tokens')),
        input_price REAL CHECK(input_price IS NULL OR input_price>=0),
        output_price REAL CHECK(output_price IS NULL OR output_price>=0),
        cache_read_price REAL CHECK(cache_read_price IS NULL OR cache_read_price>=0),
        cache_write_price REAL CHECK(cache_write_price IS NULL OR cache_write_price>=0),
        reasoning_price REAL CHECK(reasoning_price IS NULL OR reasoning_price>=0),
        currency TEXT NOT NULL DEFAULT 'USD',
        effective_from TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        effective_to TEXT)""",
    'CREATE INDEX price_entries_lookup ON price_entries(adapter, model, effective_from)',
    """CREATE TABLE usage_records (
        id TEXT PRIMARY KEY NOT NULL,
        run_id TEXT NOT NULL,
        step_execution_id TEXT REFERENCES step_executions(id),
        project_id TEXT REFERENCES projects(id),
        role TEXT NOT NULL,
        provider_config_id TEXT,
        adapter TEXT NOT NULL,
        model TEXT,
        call_index INTEGER NOT NULL CHECK(typeof(call_index)='integer' AND call_index>=1),
        started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        duration_ms INTEGER NOT NULL CHECK(typeof(duration_ms)='integer' AND duration_ms>=0),
        input_tokens INTEGER CHECK(input_tokens IS NULL OR (typeof(input_tokens)='integer' AND input_tokens>=0)),
        output_tokens INTEGER CHECK(output_tokens IS NULL OR (typeof(output_tokens)='integer' AND output_tokens>=0)),
        cache_read_tokens INTEGER CHECK(cache_read_tokens IS NULL OR (typeof(cache_read_tokens)='integer' AND cache_read_tokens>=0)),
        cache_write_tokens INTEGER CHECK(cache_write_tokens IS NULL OR (typeof(cache_write_tokens)='integer' AND cache_write_tokens>=0)),
        reasoning_tokens INTEGER CHECK(reasoning_tokens IS NULL OR (typeof(reasoning_tokens)='integer' AND reasoning_tokens>=0)),
        token_source TEXT NOT NULL CHECK(token_source IN ('provider_reported','cli_reported','estimated','unavailable')),
        billing_mode TEXT NOT NULL CHECK(billing_mode IN ('api_metered','subscription_quota','local','unknown')),
        reported_cost_usd REAL CHECK(reported_cost_usd IS NULL OR reported_cost_usd>=0),
        estimated_cost_usd REAL CHECK(estimated_cost_usd IS NULL OR estimated_cost_usd>=0),
        price_entry_id TEXT REFERENCES price_entries(id),
        currency TEXT NOT NULL DEFAULT 'USD',
        error_kind TEXT,
        retry_of TEXT,
        raw_usage TEXT NOT NULL DEFAULT '{}'
            CHECK(length(raw_usage)<=8192 AND CASE WHEN json_valid(raw_usage) THEN json_type(raw_usage)='object' ELSE 0 END),
        CHECK(token_source!='unavailable' OR (
            input_tokens IS NULL AND output_tokens IS NULL AND cache_read_tokens IS NULL
            AND cache_write_tokens IS NULL AND reasoning_tokens IS NULL AND reported_cost_usd IS NULL
        )))""",
    'CREATE INDEX usage_by_run ON usage_records(run_id, call_index)',
    'CREATE INDEX usage_by_project_started ON usage_records(project_id, started_at)',
    'CREATE INDEX usage_by_model ON usage_records(model)',
    """CREATE TABLE budgets (
        id TEXT PRIMARY KEY NOT NULL,
        scope TEXT NOT NULL CHECK(scope IN ('project','run','global')),
        scope_id TEXT,
        limit_usd REAL NOT NULL CHECK(limit_usd>=0),
        period TEXT NOT NULL CHECK(period IN ('run','month','total')),
        warn_ratio REAL NOT NULL DEFAULT 0.8 CHECK(warn_ratio>0 AND warn_ratio<=1),
        action TEXT NOT NULL DEFAULT 'warn' CHECK(action IN ('warn','block')))""",
    """CREATE TABLE budget_events (
        id TEXT PRIMARY KEY NOT NULL,
        budget_id TEXT NOT NULL REFERENCES budgets(id),
        run_id TEXT,
        kind TEXT NOT NULL CHECK(kind IN ('warn','block','override')),
        at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        details TEXT NOT NULL DEFAULT '{}'
            CHECK(CASE WHEN json_valid(details) THEN json_type(details)='object' ELSE 0 END))""",
    'INSERT INTO platform_migrations(version) VALUES(5)',
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
        if not conn.execute('SELECT 1 FROM platform_migrations WHERE version=5').fetchone():
            conn.execute('BEGIN IMMEDIATE')
            if not conn.execute('SELECT 1 FROM platform_migrations WHERE version=5').fetchone():
                for statement in ACCOUNTING_MIGRATION:
                    conn.execute(statement)
            conn.commit()
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
