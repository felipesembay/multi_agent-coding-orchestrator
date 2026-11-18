import pytest
from types import SimpleNamespace

from orchestrator.project_store import connection
from orchestrator.providers.base import CapabilityManifest
from orchestrator.workflows.snapshot import WorkflowSelection
from orchestrator.workflows.store import append_version


@pytest.fixture
def definition():
    return {
        'schema_version': 1, 'name': 'sample',
        'steps': [
            {'id': 'plan', 'type': 'plan', 'role': 'planner', 'requires': ['planning']},
            {'id': 'impl', 'type': 'implement', 'role': 'implementer',
             'requires': ['code_edit'], 'per_task': True, 'max_attempts': 3},
            {'id': 'tests', 'type': 'test', 'per_task': True, 'command_profile': 'server_default'},
            {'id': 'review', 'type': 'review', 'role': 'reviewer', 'requires': ['review'],
             'per_task': True, 'on_reject': 'impl'},
        ],
        'limits': {'max_total_steps': 200, 'max_duration_s': 14400, 'budget_usd': None},
        'approval': {'require_tests': True, 'require_reviewer': True, 'human_gate_after_plan': False},
    }


@pytest.fixture
def snapshot_case(tmp_path, monkeypatch, definition):
    monkeypatch.setenv('ORCH_DB', str(tmp_path / 'snapshot.db'))
    manifest = CapabilityManifest(
        adapter='fake', kind='agent_runtime', capabilities=['text', 'planning', 'review', 'code_edit', 'structured_output'],
        permission_modes=['read_only', 'workspace_write'], auth_modes=['none'],
        billing_mode='local', usage_source='none', verified=True,
    )
    class Registry:
        def get(self, adapter):
            if adapter != manifest.adapter:
                raise KeyError(adapter)
            return SimpleNamespace(manifest=manifest)
    with connection() as conn:
        conn.execute("INSERT INTO workflow_definitions(id,name) VALUES('wf','Workflow')")
        conn.execute("INSERT INTO provider_configs(id,kind,adapter,display_name,enabled) VALUES('pc','agent_runtime','fake','Fake',1)")
        conn.commit()
    version = append_version('wf', definition)
    selection = WorkflowSelection(workflow_version_id=version, bindings={
        'plan': {'provider_config_id': 'pc', 'model': 'plan-model'},
        'impl': {'provider_config_id': 'pc', 'permission': 'workspace_write', 'model': 'impl-model'},
        'review': {'provider_config_id': 'pc', 'model': 'review-model'},
    })
    return selection, Registry(), definition
