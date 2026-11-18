import pytest
import json
from pathlib import Path
import shlex
import sys

from orchestrator import projects
from orchestrator.worker import Worker
from orchestrator.providers.base import InvocationResult
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


@pytest.fixture
def managed_case(snapshot_case, tmp_path, monkeypatch):
    selection, registry, definition = snapshot_case
    root = tmp_path / 'projects'
    root.mkdir()
    monkeypatch.setenv('ORCH_ALLOWED_ROOTS', str(root))
    command = [sys.executable, '-c', "from pathlib import Path; assert Path('output.txt').read_text() == 'done'"]
    monkeypatch.setenv('ORCH_TEST_COMMAND', shlex.join(command))
    monkeypatch.setenv('ORCH_ALLOWED_TEST_COMMANDS', json.dumps([command]))
    monkeypatch.delenv('ORCH_WORKTREES', raising=False)
    monkeypatch.delenv('ORCH_ENV_ALLOWLIST', raising=False)
    preview = projects.preview(projects.ProjectInput(name='Snapshot test', repo_path=str(root / 'repo'), mode='create'))
    project = projects.create(projects.ProjectConfirmation(preview_token=preview['preview_token'], confirmed=True))
    request = projects.submit_request(project['id'], projects.RequestInput(title='Task', content='Original scope'))
    worker = Worker()
    worker.heartbeat()
    seen = []
    get = registry.get
    def runtime(adapter):
        provider = get(adapter)
        def invoke(request):
            seen.append(request)
            if request.role == 'planner':
                return InvocationResult(text=json.dumps({'tasks': [{'id': 'T1', 'title': 'Write output',
                    'instructions': 'Write done', 'acceptance': ['output file exists']}]}))
            if request.role == 'implementer':
                Path(request.cwd, 'output.txt').write_text('done')
                return InvocationResult(text='Updated output.txt')
            return InvocationResult(text='{"approved":true,"findings":[]}')
        provider.invoke = invoke
        return provider
    registry.get = runtime
    return selection, registry, definition, project, request, worker, seen
