from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from types import SimpleNamespace

import pytest

from orchestrator.project_store import connection
from orchestrator.workflows.snapshot import (
    WorkflowSnapshotError, load_snapshot, verify_run_snapshot,
)
from orchestrator.workflows.store import append_version



def test_immutable_version_and_provider_resolution(snapshot_case):
    selection, registry, definition = snapshot_case
    snapshot = load_snapshot(selection, registry=registry)
    before = snapshot.model_dump(mode='json')
    with connection() as conn:
        conn.execute("UPDATE provider_configs SET adapter='changed',enabled=0 WHERE id='pc'")
        conn.execute("UPDATE workflow_definitions SET name='changed',archived_at=CURRENT_TIMESTAMP WHERE id='wf'")
        conn.commit()
    assert snapshot.model_dump(mode='json') == before
    assert snapshot.providers['pc'].adapter == 'fake'
    assert snapshot.definition.name == definition['name']


def test_digest_is_canonical_and_sensitive_to_binding_and_version(snapshot_case):
    selection, registry, definition = snapshot_case
    first = load_snapshot(selection, registry=registry)
    assert first.digest() == load_snapshot(selection, registry=registry).digest()
    selection.bindings['impl'].model = 'other-model'
    assert load_snapshot(selection, registry=registry).digest() != first.digest()
    selection.workflow_version_id = append_version('wf', definition)
    assert load_snapshot(selection, registry=registry).digest() != first.digest()


def test_run_columns_and_config_must_agree(snapshot_case):
    selection, registry, _ = snapshot_case
    snapshot = load_snapshot(selection, registry=registry)
    config = {'workflow': snapshot.model_dump(mode='json')}
    row = {'workflow_version_id': snapshot.workflow_version_id,
           'bindings': json.dumps(config['workflow']['bindings']), 'workflow_digest': snapshot.digest()}
    assert verify_run_snapshot(row, config) == snapshot
    for key in row:
        changed = {**row, key: None}
        with pytest.raises(WorkflowSnapshotError):
            verify_run_snapshot(changed, config)
    changed = deepcopy(config)
    changed['workflow']['bindings']['impl']['model'] = 'tampered'
    with pytest.raises(WorkflowSnapshotError):
        verify_run_snapshot(row, changed)


def test_old_run_has_no_workflow_and_partial_metadata_is_refused():
    assert verify_run_snapshot({}, {}) is None
    with pytest.raises(WorkflowSnapshotError):
        verify_run_snapshot({'workflow_version_id': 'unpaired'}, {})


@pytest.mark.parametrize('field,value', [('enabled', 0), ('settings', '{"unknown":"not-supported"}'),
                                       ('kind', 'model_provider'), ('adapter', 'missing')])
def test_disabled_or_unsupported_provider_is_refused(snapshot_case, field, value):
    selection, registry, _ = snapshot_case
    with connection() as conn:
        conn.execute(f'UPDATE provider_configs SET {field}=? WHERE id=?', (value, 'pc'))
        conn.commit()
    with pytest.raises(WorkflowSnapshotError):
        load_snapshot(selection, registry=registry)


def test_archived_workflow_and_missing_version_are_refused(snapshot_case):
    selection, registry, _ = snapshot_case
    with connection() as conn:
        conn.execute("UPDATE workflow_definitions SET archived_at=CURRENT_TIMESTAMP WHERE id='wf'")
        conn.commit()
    with pytest.raises(WorkflowSnapshotError):
        load_snapshot(selection, registry=registry)
    selection.workflow_version_id = 'missing'
    with pytest.raises(WorkflowSnapshotError):
        load_snapshot(selection, registry=registry)


@pytest.mark.parametrize('feature', ['gate', 'budget', 'fallback', 'parameters'])
def test_unimplemented_execution_features_fail_before_queueing(snapshot_case, feature):
    selection, registry, definition = snapshot_case
    if feature == 'gate':
        definition['approval']['human_gate_after_plan'] = True
    elif feature == 'budget':
        definition['limits']['budget_usd'] = 1.0
    elif feature == 'fallback':
        from orchestrator.workflows.schema import FallbackBinding
        selection.bindings['plan'].fallbacks = [FallbackBinding(provider_config_id='pc', on=['unavailable'])]
    else:
        selection.bindings['plan'].parameters = {'unknown': True}
    if feature in ('gate', 'budget'):
        selection.workflow_version_id = append_version('wf', definition)
    with pytest.raises(WorkflowSnapshotError):
        load_snapshot(selection, registry=registry)


def test_append_validates_body_and_system_read_only(snapshot_case):
    _, _, definition = snapshot_case
    definition['steps'][1]['max_attempts'] = 0
    with pytest.raises(ValueError):
        append_version('wf', definition)
    with connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM workflow_versions').fetchone()[0] == 1
        conn.execute("UPDATE workflow_definitions SET is_preset=1 WHERE id='wf'")
        conn.commit()
    with pytest.raises(WorkflowSnapshotError):
        append_version('wf', {})


def test_append_versions_is_safe_under_concurrent_writers(snapshot_case):
    _, _, definition = snapshot_case
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: append_version('wf', definition), range(4)))
    assert len(set(ids)) == 4
    with connection() as conn:
        assert [r[0] for r in conn.execute('SELECT version FROM workflow_versions ORDER BY version')] == [1, 2, 3, 4, 5]


def test_dictionary_manifest_is_supported(snapshot_case):
    selection, registry, _ = snapshot_case
    manifest = registry.get('fake').manifest.model_dump(mode='json')
    registry.get = lambda adapter: SimpleNamespace(manifest=manifest)
    assert load_snapshot(selection, registry=registry).providers['pc'].kind == 'agent_runtime'


def test_nonintegrated_credential_reference_is_not_copied(snapshot_case):
    selection, registry, _ = snapshot_case
    with connection() as conn:
        conn.execute("UPDATE provider_configs SET credential_ref='reference-not-implemented' WHERE id='pc'")
        conn.commit()
    with pytest.raises(WorkflowSnapshotError) as caught:
        load_snapshot(selection, registry=registry)
    assert 'reference-not-implemented' not in str(caught.value)


def test_version_schema_and_digest_are_verified(snapshot_case):
    selection, registry, definition = snapshot_case
    with connection() as conn:
        conn.execute('''INSERT INTO workflow_versions(id,definition_id,version,schema_version,body,digest)
                        VALUES('bad-version','wf',2,2,?,?)''', (json.dumps(definition), '0' * 64))
        conn.commit()
    selection.workflow_version_id = 'bad-version'
    with pytest.raises(WorkflowSnapshotError):
        load_snapshot(selection, registry=registry)
