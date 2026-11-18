"""Internal append-only version writer; HTTP CRUD belongs to V2-WF-008."""
import uuid

from ..project_store import connection
from .schema import WorkflowDefinition
from .snapshot import WorkflowSnapshotError, canonical, digest


def append_version(definition_id, body):
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
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
        conn.commit()
        return version_id
