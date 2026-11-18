-- Frozen schema from caee20e, before V2-WF-002; no runtime migration imports.
BEGIN TRANSACTION;
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    at TEXT DEFAULT CURRENT_TIMESTAMP,
    stage TEXT,
    payload TEXT
);
CREATE TABLE execution_worker (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), worker_id TEXT NOT NULL,
        pid INTEGER NOT NULL, process_start TEXT NOT NULL, boot_id TEXT NOT NULL,
        heartbeat REAL NOT NULL);
CREATE TABLE managed_runs (
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
        dispatch_token TEXT NOT NULL, orphaned INTEGER NOT NULL DEFAULT 0);
CREATE TABLE platform_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        action TEXT NOT NULL, project_id TEXT, details TEXT NOT NULL);
CREATE TABLE platform_migrations (version INTEGER PRIMARY KEY);
INSERT INTO "platform_migrations" VALUES(1);
INSERT INTO "platform_migrations" VALUES(2);
INSERT INTO "platform_migrations" VALUES(3);
CREATE TABLE project_previews (
        token TEXT PRIMARY KEY, payload TEXT NOT NULL, parent_device INTEGER NOT NULL,
        parent_inode INTEGER NOT NULL, expires_at REAL NOT NULL,
        project_id TEXT REFERENCES projects(id));
CREATE TABLE project_requests (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        title TEXT NOT NULL, content TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'submitted',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE projects (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
        objectives TEXT NOT NULL, repository_id TEXT NOT NULL REFERENCES repositories(id),
        state TEXT NOT NULL DEFAULT 'active' CHECK(state IN ('active','archived')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, deleted_at TEXT);
CREATE TABLE repositories (
        id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, git_common_dir TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
DELETE FROM "sqlite_sequence";
CREATE INDEX requests_by_project ON project_requests(project_id, created_at);
CREATE UNIQUE INDEX one_active_run_per_repository
        ON managed_runs(repo_identity) WHERE status IN ('queued','running') OR orphaned=1;
CREATE INDEX runs_by_project ON managed_runs(project_id,created_at);
COMMIT;
