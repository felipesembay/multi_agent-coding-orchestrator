import json

import pytest

from orchestrator.projects import audit
from orchestrator.project_store import connection
from orchestrator.policy.audit import AuditError


EVENTS=[
    ('workflow.created',{'workflow_id':'wf-1'}),
    ('workflow.version_created',{'workflow_id':'wf-1','version_id':'wv-1'}),
    ('provider.configured',{'provider_config_id':'pc-1','adapter':'openrouter'}),
    ('credential.set',{'provider_config_id':'pc-1','adapter':'openrouter',
                       'credential_ref':'multi-agent-orchestrator:openrouter:pc-1'}),
    ('credential.removed',{'provider_config_id':'pc-1','adapter':'openrouter'}),
    ('approval.decided',{'approval_id':'approval-1','decision':'approve','kind':'resume'}),
    ('budget.override',{'budget_id':'budget-1','approval_id':'approval-1'}),
    ('run.resumed',{'run_id':'run-123456789abc','approval_id':'approval-1','checkpoint_id':'checkpoint-1'}),
]


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch,tmp_path):
    monkeypatch.setenv('ORCH_DB',str(tmp_path/'events.db'))


@pytest.mark.parametrize('action,payload',EVENTS)
def test_each_extended_action_has_validated_audit_record(action,payload):
    with connection() as conn:
        audit(conn,action,**payload);conn.commit()
        row=conn.execute('SELECT action,details,at FROM platform_audit').fetchone()
        assert row['action']==action and json.loads(row['details'])==payload
        assert row['at']


@pytest.mark.parametrize('action,payload',EVENTS)
def test_secrets_nested_payloads_and_unknown_fields_are_rejected_without_echo(action,payload):
    with connection() as conn:
        for extra in ({'api_key':'sentinel-never-store'}, {'prompt':'sentinel-never-store'},
                      {'settings':{'authorization':'sentinel-never-store'}}):
            with pytest.raises(AuditError) as caught: audit(conn,action,**payload,**extra)
            assert 'sentinel' not in str(caught.value)
        assert conn.execute('SELECT COUNT(*) FROM platform_audit').fetchone()[0]==0


@pytest.mark.parametrize('action,payload',[
    ('workflow.created',{}), ('provider.configured',{'provider_config_id':'pc-1','adapter':'/private/path'}),
    ('credential.set',{'provider_config_id':'pc-1','adapter':'openrouter','credential_ref':'sentinel-never-store'}),
    ('approval.decided',{'approval_id':'approval-1','decision':'silently-auto-approve'}),
    ('run.resumed',{'run_id':'run-123456789abc'}), ('credential.typo',{}),
    ('budget.override',{'budget_id':'budget-1','approval_id':{'secret':'sentinel-never-store'}}),
])
def test_invalid_or_unlinked_metadata_is_not_an_auditable_decision(action,payload):
    with connection() as conn:
        with pytest.raises(AuditError): audit(conn,action,**payload)
        assert conn.execute('SELECT COUNT(*) FROM platform_audit').fetchone()[0]==0


def test_legacy_audit_and_transaction_atomicity_are_preserved():
    with connection() as conn:
        audit(conn,'project.preview',mode='existing',path='/tmp/allowed');conn.commit()
    with pytest.raises(AuditError):
        with connection() as conn:
            conn.execute("INSERT INTO workflow_definitions(id,name) VALUES('wf-new','New')")
            audit(conn,'workflow.created',workflow_id='wf-new',secret='sentinel-never-store')
            conn.commit()
    with connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM workflow_definitions WHERE id='wf-new'").fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM platform_audit').fetchone()[0]==1
