"""Internal append-only version writer; HTTP CRUD belongs to V2-WF-008."""
import uuid
from ..projects import ProjectError, audit

from ..project_store import connection
from .schema import WorkflowDefinition
from .snapshot import WorkflowSnapshotError, canonical, digest


def _append(conn, definition_id, body):
    definition = conn.execute('SELECT * FROM workflow_definitions WHERE id=?', (definition_id,)).fetchone()
    if definition is None or definition['archived_at'] is not None or definition['is_preset']:
        raise WorkflowSnapshotError('Workflow missing, archived or read only')
    parsed = WorkflowDefinition.model_validate(body.model_dump() if isinstance(body, WorkflowDefinition) else body)
    payload = parsed.model_dump(mode='json')
    version = conn.execute('SELECT COALESCE(MAX(version),0)+1 FROM workflow_versions WHERE definition_id=?',
                           (definition_id,)).fetchone()[0]
    version_id = 'wv-' + uuid.uuid4().hex
    conn.execute('''INSERT INTO workflow_versions(id,definition_id,version,schema_version,body,digest)
                    VALUES(?,?,?,?,?,?)''',
                 (version_id, definition_id, version, parsed.schema_version, canonical(payload), digest(payload)))
    audit(conn, 'workflow.version_created', None, workflow_id=definition_id, version_id=version_id)
    return version_id


def append_version(definition_id, body):
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        version_id = _append(conn, definition_id, body)
        conn.commit()
        return version_id


def _version(row):
    body = WorkflowDefinition.model_validate_json(row['body']).model_dump(mode='json')
    if row['digest'] != digest(body):
        raise WorkflowSnapshotError('Workflow version integrity check failed')
    return dict(id=row['id'], version=row['version'], schema_version=row['schema_version'],
                definition=body, digest=row['digest'], created_at=row['created_at'])


def get_workflow(workflow_id, conn=None):
    if conn is None:
        with connection() as owned:
            return get_workflow(workflow_id, owned)
    row = conn.execute('SELECT * FROM workflow_definitions WHERE id=?', (workflow_id,)).fetchone()
    if row is None:
        raise ProjectError('Workflow não encontrado.', 404)
    latest = conn.execute('SELECT * FROM workflow_versions WHERE definition_id=? ORDER BY version DESC LIMIT 1',
                          (workflow_id,)).fetchone()
    return dict(id=row['id'], name=row['name'], description=row['description'],
                read_only=bool(row['is_preset']), archived=row['archived_at'] is not None,
                latest_version=_version(latest) if latest else None)


def list_workflows():
    with connection() as conn:
        ids = [r['id'] for r in conn.execute('SELECT id FROM workflow_definitions WHERE archived_at IS NULL ORDER BY created_at,id')]
        return [get_workflow(key, conn) for key in ids]


def versions(workflow_id):
    with connection() as conn:
        get_workflow(workflow_id, conn)
        return [_version(r) for r in conn.execute('SELECT * FROM workflow_versions WHERE definition_id=? ORDER BY version', (workflow_id,))]


def create_workflow(body, description=''):
    parsed = WorkflowDefinition.model_validate(body.model_dump() if isinstance(body, WorkflowDefinition) else body)
    key = 'wf-' + uuid.uuid4().hex
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('INSERT INTO workflow_definitions(id,name,description) VALUES(?,?,?)', (key, parsed.name, description))
        _append(conn, key, parsed)
        audit(conn, 'workflow.created', None, workflow_id=key)
        result = get_workflow(key, conn)
        conn.commit()
        return result
