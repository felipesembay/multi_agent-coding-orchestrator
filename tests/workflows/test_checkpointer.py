import os
import stat
from pathlib import Path
from contextlib import contextmanager
import sqlite3

import pytest

from orchestrator import core
from orchestrator.project_store import connection
from orchestrator.resilience.checkpointer import checkpoint_config, checkpoint_path, open_checkpointer, CheckpointError
from orchestrator.workflows.execution import execute_snapshot
from orchestrator.workflows.snapshot import WorkflowSnapshot
from .test_run_snapshot import queue, dispatch


def test_managed_workflow_checkpoint_survives_reopen_without_reexecuting(managed_case,monkeypatch):
    _,registry,_,project,_,_,seen=managed_case
    run_id,config,_=queue(managed_case)
    assert dispatch(managed_case,run_id,monkeypatch)==0
    called=len(seen)
    assert checkpoint_path()!=Path(core.db_path()).resolve()
    with open_checkpointer() as saver:
        item=saver.get_tuple(checkpoint_config(run_id))
        values=item.checkpoint['channel_values']
        assert values['status']=='ready_for_human_review'
        assert values['plan']['tasks'][0]['id']=='T1'
        assert values['workflow_attempts']=={'impl:0':1}
        assert item.metadata['workflow_digest']==WorkflowSnapshot.model_validate(config['workflow']).digest()
        assert len(list(saver.list(checkpoint_config(run_id))))>=6
        assert saver.get_tuple(checkpoint_config('run-111111111111')) is None
    assert len(seen)==called
    assert stat.S_IMODE(os.stat(checkpoint_path()).st_mode)==0o600
    monkeypatch.setattr(core,'prepare',lambda *args:pytest.fail('Checkpoint must block repeated effects before prepare'))
    with pytest.raises(CheckpointError,match='inspection'):
        execute_snapshot(project['repo_path'],'scope',run_id=run_id,
            snapshot=WorkflowSnapshot.model_validate(config['workflow']),config=config,registry=registry)
    assert len(seen)==called


def test_failed_node_keeps_prior_checkpoint_without_replaying(managed_case,monkeypatch):
    _,registry,_,_,_,_,seen=managed_case
    run_id,_,_=queue(managed_case)
    get=registry.get
    def failing(adapter):
        provider=get(adapter)
        def invoke(req):
            seen.append(req)
            raise RuntimeError('fake crash')
        provider.invoke=invoke
        return provider
    registry.get=failing
    assert dispatch(managed_case,run_id,monkeypatch)==1
    with open_checkpointer() as saver:
        item=saver.get_tuple(checkpoint_config(run_id))
        assert item is not None
        assert item.checkpoint['channel_values']['workflow_steps']==0
        assert item.checkpoint['channel_values']['workflow_outputs']=={}
    assert len(seen)==1


def test_corrupt_checkpoint_does_not_touch_catalog_or_start_agents(managed_case,monkeypatch):
    run_id,_,_=queue(managed_case)
    checkpoint_path().write_bytes(b'not a sqlite database')
    monkeypatch.setattr(core,'prepare',lambda *args:pytest.fail('No worktree before checkpoint storage is ready'))
    assert dispatch(managed_case,run_id,monkeypatch)==1
    with connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM managed_runs').fetchone()[0]==1
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert managed_case[-1]==[]


def test_checkpoint_path_refuses_symlink_and_does_not_change_target(tmp_path,monkeypatch):
    monkeypatch.setenv('ORCH_DB',str(tmp_path/'events.db'))
    target=tmp_path/'target';target.write_text('untouched')
    checkpoint_path().symlink_to(target)
    with pytest.raises(CheckpointError):
        with open_checkpointer(): pass
    assert target.read_text()=='untouched'


def test_checkpoint_write_failure_stops_before_next_side_effect(managed_case,monkeypatch):
    run_id,_,_=queue(managed_case)
    @contextmanager
    def failing_store():
        with open_checkpointer() as saver:
            put=saver.put
            def fail_after_plan(config,checkpoint,metadata,new_versions):
                if checkpoint['channel_values'].get('plan'):
                    raise sqlite3.OperationalError('simulated checkpoint failure')
                return put(config,checkpoint,metadata,new_versions)
            saver.put=fail_after_plan
            yield saver
    monkeypatch.setattr('orchestrator.workflows.execution.open_checkpointer',failing_store)
    assert dispatch(managed_case,run_id,monkeypatch)==1
    assert [req.role for req in managed_case[-1]]==['planner']


@pytest.mark.parametrize('run_id',['../events.db','other-run','run-abc',''])
def test_checkpoint_identity_is_server_run_id(run_id):
    with pytest.raises(CheckpointError): checkpoint_config(run_id)
