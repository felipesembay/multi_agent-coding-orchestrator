"""Upgrade a frozen pre-v4 database, without agents or production data."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest

from orchestrator import project_store


V3_SCHEMA = Path(__file__).parents[1] / 'fixtures' / 'platform_v3.sql'
NEW_TABLES = {'workflow_definitions', 'workflow_versions', 'provider_configs'}
NEW_COLUMNS = {'workflow_version_id', 'bindings', 'workflow_digest'}


def snapshot(conn):
    names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
             if not row[0].startswith('sqlite_')]
    return {name: [dict(row) for row in conn.execute(f'SELECT * FROM {name} ORDER BY rowid')]
            for name in names}


@pytest.fixture
def legacy_db(tmp_path, monkeypatch):
    path = tmp_path / 'v3.db'
    monkeypatch.setenv('ORCH_DB', str(path))
    with sqlite3.connect(path) as conn:
        conn.executescript(V3_SCHEMA.read_text())
        conn.execute("INSERT INTO repositories(id,path,git_common_dir) VALUES('repo','/tmp/v3-repo','/tmp/v3-repo/.git')")
        conn.execute("INSERT INTO projects(id,name,description,objectives,repository_id,deleted_at) VALUES('p','Projeto','Descrição','Objetivos','repo','2026-11-17')")
        conn.execute("INSERT INTO project_requests(id,project_id,title,content) VALUES('q','p','Título','Conteúdo')")
        config = json.dumps({'planner': 'claude', 'implementer': 'antigravity',
                             'environment_allowlist': {'tests': ['APP_MODE']}, 'max_attempts': 3})
        for index, status in enumerate(('queued', 'running', 'ready_for_human_review', 'blocked', 'failed', 'interrupted')):
            conn.execute('''INSERT INTO managed_runs(run_id,project_id,request_id,request_title,
                scope,repo,repo_identity,config,idempotency_key,status,dispatch_token,orphaned,
                worktree,error,result,pid,process_start,boot_id,worker_id,heartbeat)
                VALUES(?, 'p','q','Título','Escopo','/tmp/v3-repo',?,?,?,?,'dispatch',?,
                       '/tmp/worktree','example error','{}',123,'start','boot','worker',123.5)''',
                         (f'run-{index}', f'identity-{index}', config, f'key-{index}', status, int(status == 'interrupted')))
            conn.execute("INSERT INTO events(run_id,stage,payload) VALUES(?, 'started', ?)",
                         (f'run-{index}', json.dumps({'scope': 'Escopo', 'message': 'evento legado'})))
        conn.execute("INSERT INTO events(run_id,stage,payload) VALUES('cli-legacy','plan','{}')")
        conn.execute("INSERT INTO platform_audit(action,project_id,details) VALUES('project.deleted','p','{}')")
        conn.execute("INSERT INTO project_previews(token,payload,parent_device,parent_inode,expires_at,project_id) VALUES('preview','{}',1,2,12345.0,'p')")
        conn.execute("INSERT INTO execution_worker VALUES(1,'worker',123,'start','boot',123.5)")
    return path


def test_upgrade_preserves_every_legacy_row_and_adds_null_columns(legacy_db):
    with sqlite3.connect(legacy_db) as old:
        old.row_factory = sqlite3.Row
        before = snapshot(old)
        old_columns = [r['name'] for r in old.execute('PRAGMA table_info(managed_runs)')]
        old_indexes = old.execute("SELECT name,sql FROM sqlite_master WHERE type='index'").fetchall()
    with project_store.connection() as conn:
        assert [r[0] for r in conn.execute('SELECT version FROM platform_migrations ORDER BY version')] == [1, 2, 3, 4]
        after = snapshot(conn)
        for table, rows in before.items():
            if table == 'platform_migrations':
                assert after[table][:3] == rows
            elif table == 'managed_runs':
                assert [{key: row[key] for key in old_columns} for row in after[table]] == rows
                assert all(row[key] is None for row in after[table] for key in NEW_COLUMNS)
            else:
                assert after[table] == rows
        assert NEW_TABLES <= set(after)
        assert all(after[name] == [] for name in NEW_TABLES)  # no default/preset decision
        for name, sql in old_indexes:
            assert conn.execute('SELECT sql FROM sqlite_master WHERE name=?', (name,)).fetchone()[0] == sql
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert conn.execute("INSERT INTO events(run_id,stage,payload) VALUES('new-cli','plan','{}')").lastrowid == 8


def test_fresh_database_and_reopen_are_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv('ORCH_DB', str(tmp_path / 'fresh.db'))
    with project_store.connection() as conn:
        assert NEW_TABLES <= set(snapshot(conn))
        before = snapshot(conn)
        schema = conn.execute('SELECT name,sql FROM sqlite_master ORDER BY name').fetchall()
    for _ in range(3):
        with project_store.connection() as conn:
            assert snapshot(conn) == before
            assert conn.execute('SELECT name,sql FROM sqlite_master ORDER BY name').fetchall() == schema


def test_concurrent_upgrade_only_applies_v4_once(legacy_db):
    barrier = Barrier(4)
    def open_database(_):
        barrier.wait(timeout=10)
        with project_store.connection() as conn:
            return conn.execute('SELECT COUNT(*) FROM platform_migrations WHERE version=4').fetchone()[0]
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(open_database, range(4))) == [1, 1, 1, 1]


def test_failure_rolls_back_all_v4_ddl_and_can_retry(legacy_db, monkeypatch):
    statements = project_store.WORKFLOW_MIGRATION
    with monkeypatch.context() as patch:
        patch.setattr(project_store, 'WORKFLOW_MIGRATION', [*statements[:-1], 'INVALID SQL', statements[-1]])
        with pytest.raises(sqlite3.OperationalError):
            with project_store.connection():
                pytest.fail('Migration must fail before yielding')
    with sqlite3.connect(legacy_db) as conn:
        assert conn.execute('SELECT MAX(version) FROM platform_migrations').fetchone()[0] == 3
        assert not NEW_TABLES.intersection(row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"))
        assert not NEW_COLUMNS.intersection(row[1] for row in conn.execute('PRAGMA table_info(managed_runs)'))
        assert conn.execute('SELECT COUNT(*) FROM managed_runs').fetchone()[0] == 6
    with project_store.connection() as conn:
        assert conn.execute('SELECT MAX(version) FROM platform_migrations').fetchone()[0] == 4


def insert_version(conn, definition):
    from orchestrator.workflows.schema import WorkflowDefinition
    body = WorkflowDefinition.model_validate(definition).model_dump_json()
    conn.execute("INSERT INTO workflow_definitions(id,name) VALUES('wf','Sample')")
    conn.execute('''INSERT INTO workflow_versions(id,definition_id,version,schema_version,body,digest)
                    VALUES('v1','wf',1,1,?,?)''', (body, hashlib.sha256(body.encode()).hexdigest()))


def test_version_link_and_constraints(legacy_db, definition):
    with project_store.connection() as conn:
        insert_version(conn, definition)
        conn.execute("UPDATE managed_runs SET workflow_version_id='v1',bindings='{}',workflow_digest=? WHERE run_id='run-0'", ('a' * 64,))
        assert conn.execute("SELECT workflow_version_id FROM managed_runs WHERE run_id='run-0'").fetchone()[0] == 'v1'
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE managed_runs SET workflow_version_id='missing' WHERE run_id='run-0'")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM workflow_definitions WHERE id='wf'")
        conn.commit()


@pytest.mark.parametrize('statement', [
    "UPDATE workflow_versions SET body='{}' WHERE id='v1'",
    "UPDATE workflow_versions SET digest='different' WHERE id='v1'",
    "DELETE FROM workflow_versions WHERE id='v1'",
    "INSERT INTO workflow_versions SELECT 'v2',definition_id,version,schema_version,body,digest,created_at FROM workflow_versions",
    "INSERT OR REPLACE INTO workflow_versions SELECT id,definition_id,version,schema_version,'{}',digest,created_at FROM workflow_versions",
    "INSERT OR REPLACE INTO workflow_versions SELECT 'different-id',definition_id,version,schema_version,'{}',digest,created_at FROM workflow_versions",
    "UPDATE OR REPLACE workflow_versions SET body='{}' WHERE id='v1'",
])
def test_versions_are_immutable_and_numbered_uniquely(legacy_db, definition, statement):
    with project_store.connection() as conn:
        insert_version(conn, definition)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(statement)


@pytest.mark.parametrize('field,value', [
    ('kind', 'unknown'), ('enabled', 2), ('settings', 'invalid json'), ('settings', '[]'),
])
def test_provider_configuration_basic_constraints(legacy_db, field, value):
    values = dict(id='pc', kind='agent_runtime', adapter='claude_code', display_name='Claude', settings='{}', enabled=0)
    values[field] = value
    with project_store.connection() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"INSERT INTO provider_configs({','.join(values)}) VALUES({','.join('?' for _ in values)})", tuple(values.values()))


def test_provider_reference_is_optional_and_preserved(legacy_db):
    with project_store.connection() as conn:
        conn.execute("INSERT INTO provider_configs(id,kind,adapter,display_name) VALUES('cli','agent_runtime','claude_code','Claude')")
        conn.execute("INSERT INTO provider_configs(id,kind,adapter,display_name,credential_ref) VALUES('api','model_provider','openrouter','OpenRouter','keyring-reference-only')")
        conn.commit()
    with project_store.connection() as conn:
        assert conn.execute("SELECT credential_ref FROM provider_configs WHERE id='cli'").fetchone()[0] is None
        assert conn.execute("SELECT credential_ref FROM provider_configs WHERE id='api'").fetchone()[0] == 'keyring-reference-only'


@pytest.mark.parametrize('field,value', [
    ('body', 'invalid json'), ('body', '[]'), ('digest', 'invalid'),
    ('schema_version', 0), ('version', 0), ('definition_id', 'missing'),
])
def test_version_basic_integrity(legacy_db, definition, field, value):
    from orchestrator.workflows.schema import WorkflowDefinition
    body = WorkflowDefinition.model_validate(definition).model_dump_json()
    values = dict(id='v1', definition_id='wf', version=1, schema_version=1,
                  body=body, digest=hashlib.sha256(body.encode()).hexdigest())
    values[field] = value
    with project_store.connection() as conn:
        conn.execute("INSERT INTO workflow_definitions(id,name) VALUES('wf','Sample')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"INSERT INTO workflow_versions({','.join(values)}) VALUES({','.join('?' for _ in values)})", tuple(values.values()))


@pytest.mark.parametrize('field,value', [('bindings', 'invalid'), ('bindings', '[]'), ('workflow_digest', 'invalid')])
def test_new_run_fields_reject_malformed_values(legacy_db, field, value):
    with project_store.connection() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"UPDATE managed_runs SET {field}=? WHERE run_id='run-0'", (value,))
