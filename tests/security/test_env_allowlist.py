"""Real subprocess environments are bounded; no actual agent CLI is invoked."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import Mock

import pytest

from orchestrator import core, projects, repository_lock
from orchestrator.policy.env import (EnvironmentPolicyError, environment_config,
                                     environment_scope, parse_allowlist, safe_env)
from orchestrator.providers.base import CapabilityManifest, CommandRuntime, InvocationRequest, InvocationResult
from orchestrator.worker import Worker


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    monkeypatch.delenv('ORCH_ENV_ALLOWLIST', raising=False)
    monkeypatch.delenv('ORCH_DISPATCH_TOKEN', raising=False)


def test_default_environment_is_an_exact_allowlist():
    source = dict(PATH='/usr/bin', HOME='/tmp/home', LANG='C', LC_CTYPE='C.UTF-8',
                  XDG_CONFIG_HOME='/tmp/config', XDG_CACHE_HOME='/tmp/cache',
                  SENTINEL_SECRET='do-not-pass', ANTHROPIC_API_KEY='do-not-pass',
                  OPENAI_API_KEY='do-not-pass', LC_SECRET='do-not-pass', XDG_SECRET='do-not-pass',
                  PYTHONPATH='/untrusted', LD_PRELOAD='/untrusted', ORCH_DB='/private/events.db')
    env = safe_env('tests', source=source)
    for key in ('PATH', 'HOME', 'LANG', 'LC_CTYPE', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME'):
        assert env[key] == source[key]
    for key in ('SENTINEL_SECRET', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'LC_SECRET',
                'XDG_SECRET', 'PYTHONPATH', 'LD_PRELOAD', 'ORCH_DB'):
        assert key not in env
    assert env['GIT_CONFIG_NOSYSTEM'] == '1'
    assert env['GIT_CONFIG_GLOBAL'] == os.devnull
    assert source['SENTINEL_SECRET'] == 'do-not-pass'  # Parent not mutated.


def test_config_extensions_are_scoped_not_shared_between_agents_or_tests():
    config = parse_allowlist('{"claude_code":["CUSTOM_CLI_DIR"],"tests":["TEST_FIXTURE_DIR"]}')
    source = {'CUSTOM_CLI_DIR': '/tmp/cli', 'TEST_FIXTURE_DIR': '/tmp/tests'}
    with environment_config(config):
        assert safe_env('claude_code', source=source)['CUSTOM_CLI_DIR'] == '/tmp/cli'
        assert 'CUSTOM_CLI_DIR' not in safe_env('codex_cli', source=source)
        assert 'CUSTOM_CLI_DIR' not in safe_env('tests', source=source)
        assert safe_env('tests', source=source)['TEST_FIXTURE_DIR'] == '/tmp/tests'
    assert 'CUSTOM_CLI_DIR' not in safe_env('claude_code', source=source)


@pytest.mark.parametrize('raw', ['not-json-secret', '[]', '{"tests":"PATH"}', '{"*":["PATH"]}',
    '{"tests":["*"]}', '{"tests":["SENTINEL_SECRET"]}', '{"tests":["ORCH_DB"]}',
    '{"tests":["LD_PRELOAD"]}', '{"tests":["GIT_CONFIG_COUNT"]}'])
def test_invalid_policy_fails_closed_without_echoing_configuration(raw):
    with pytest.raises(EnvironmentPolicyError) as caught:
        parse_allowlist(raw)
    assert raw not in str(caught.value)


def test_dispatch_marker_survives_but_other_worker_controls_do_not(monkeypatch):
    monkeypatch.setenv('ORCH_DISPATCH_TOKEN', 'internal-process-proof')
    source = {'ORCH_DISPATCH_TOKEN': 'not-trusted-override', 'ORCH_WORKER_ID': 'worker',
              'ORCH_DB': '/tmp/db', 'ORCH_ALLOWED_ROOTS': '/tmp/repos'}
    env = safe_env('tests', source=source)
    assert env['ORCH_DISPATCH_TOKEN'] == 'internal-process-proof'
    assert 'ORCH_WORKER_ID' not in env and 'ORCH_DB' not in env and 'ORCH_ALLOWED_ROOTS' not in env


def test_manifest_environment_names_are_scoped_at_runtime(monkeypatch):
    monkeypatch.setenv('CUSTOM_CLI_DIR', '/tmp/cli-config')
    monkeypatch.setenv('SENTINEL_SECRET', 'never-allow')
    class FakeRuntime(CommandRuntime):
        provider = 'fake_cli'
        manifest = CapabilityManifest(adapter='fake_cli', kind='agent_runtime', capabilities={'text'},
            permission_modes=['read_only'], auth_modes=['none'], billing_mode='local',
            usage_source='none', verified=False, environment_variables={'CUSTOM_CLI_DIR'})
        def _invoke(self, req):
            return InvocationResult(text=self._run(['fake-cli'], req))
    runner = Mock(return_value='ok')
    FakeRuntime(runner).invoke(InvocationRequest(prompt='task', cwd='/tmp', permission='read_only'))
    env = runner.call_args.kwargs['env']
    assert env['CUSTOM_CLI_DIR'] == '/tmp/cli-config'
    assert 'SENTINEL_SECRET' not in env
    assert 'CUSTOM_CLI_DIR' not in safe_env('tests')


def test_real_fake_agent_proc_environment_is_clean(monkeypatch, tmp_path):
    monkeypatch.setenv('SENTINEL_SECRET', 'worker-secret-sentinel')
    monkeypatch.setenv('OPENAI_API_KEY', 'worker-api-sentinel')
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/tmp/private-session-bus')
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('ORCH_DISPATCH_TOKEN', 'generated-group-proof')
    release = tmp_path / 'release'
    ready = tmp_path / 'ready'
    code = ('import time; from pathlib import Path\n'
            f'Path({str(ready)!r}).touch()\n'
            f'while not Path({str(release)!r}).exists(): time.sleep(.01)\n'
            'print("fake-ok")\n')
    real_popen = subprocess.Popen
    inspected = []
    def inspect(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            assert ready.exists(), 'Fake process must finish exec before /proc inspection'
            raw = Path(f'/proc/{process.pid}/environ').read_bytes().split(b'\x00')
            env = dict(item.split(b'=', 1) for item in raw if b'=' in item)
            assert env.get(b'SENTINEL_SECRET') is None and env.get(b'OPENAI_API_KEY') is None
            assert b'DBUS_SESSION_BUS_ADDRESS' not in env
            assert env[b'HOME'] == str(tmp_path).encode()
            assert env[b'ORCH_DISPATCH_TOKEN'] == b'generated-group-proof'
            inspected.append(process.pid)
        except BaseException:
            process.kill()
            process.wait()
            raise
        finally:
            release.touch()
        return process
    monkeypatch.setattr(subprocess, 'Popen', inspect)
    class FakeRuntime(CommandRuntime):
        provider = 'fake_cli'
        manifest = CapabilityManifest(adapter='fake_cli', kind='agent_runtime', capabilities={'text'},
            permission_modes=['read_only'], auth_modes=['none'], billing_mode='local', usage_source='none', verified=False)
        def _invoke(self, req):
            return InvocationResult(text=self._run([sys.executable, '-c', code], req))
    result = FakeRuntime(core.run_command).invoke(InvocationRequest(prompt='task', cwd=str(tmp_path), permission='read_only'))
    assert result.text.strip() == 'fake-ok'
    assert len(inspected) == 1


def test_keyring_bus_is_reserved_to_runner_and_cannot_be_forwarded_by_allowlist(monkeypatch):
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/tmp/private-session-bus')
    assert 'DBUS_SESSION_BUS_ADDRESS' in safe_env('runner')
    for scope in ('tests','git','claude_code','codex_cli','antigravity'):
        assert 'DBUS_SESSION_BUS_ADDRESS' not in safe_env(scope)
    with pytest.raises(EnvironmentPolicyError):
        parse_allowlist({'tests':['DBUS_SESSION_BUS_ADDRESS']})


def test_worker_spawn_is_clean_and_retains_frozen_downstream_configuration(monkeypatch, tmp_path):
    fake = tmp_path / 'fake-python'
    ready = tmp_path / 'ready'
    fake.write_text(f'#!{sys.executable}\nimport time\nfrom pathlib import Path\nPath({str(ready)!r}).touch()\ntime.sleep(30)\n')
    fake.chmod(0o755)
    monkeypatch.setenv('SENTINEL_SECRET', 'never-forward')
    monkeypatch.setenv('OPENAI_API_KEY', 'never-forward-api')
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/tmp/private-session-bus')
    monkeypatch.setenv('ORCH_DB', str(tmp_path / 'events.db'))
    monkeypatch.setenv('ORCH_ALLOWED_ROOTS', str(tmp_path))
    monkeypatch.setenv('CUSTOM_CLI_DIR', '/tmp/selected-config')
    monkeypatch.setenv('ORCH_ENV_ALLOWLIST', '{"tests":["WRONG_DIR"]}')
    policy = {'claude_code': ['CUSTOM_CLI_DIR']}
    worker = Worker()
    monkeypatch.setattr('orchestrator.worker.sys.executable', str(fake))
    child = worker.spawn({'run_id': 'fake-run', 'dispatch_token': 'proof',
                          'config': json.dumps({'environment_allowlist': policy})})
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        assert ready.exists(), 'Fake worker must finish exec before /proc inspection'
        raw = Path(f'/proc/{child.pid}/environ').read_bytes().split(b'\x00')
        env = dict(item.split(b'=', 1) for item in raw if b'=' in item)
        assert env.get(b'SENTINEL_SECRET') is None and env.get(b'OPENAI_API_KEY') is None
        assert env[b'ORCH_DISPATCH_TOKEN'] == b'proof'
        assert env[b'DBUS_SESSION_BUS_ADDRESS'] == b'unix:path=/tmp/private-session-bus'
        assert env[b'ORCH_WORKER_ID'] == worker.id.encode()
        assert env[b'ORCH_ALLOWED_ROOTS'] == str(tmp_path).encode()
        assert env[b'CUSTOM_CLI_DIR'] == b'/tmp/selected-config'
        assert json.loads(env[b'ORCH_ENV_ALLOWLIST']) == policy
    finally:
        child.kill()
        child.wait(timeout=5)


def test_core_test_command_and_git_helpers_do_not_inherit_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv('SENTINEL_SECRET', 'must-not-pass')
    monkeypatch.setenv('CODEX_HOME', '/private/codex')
    monkeypatch.setenv('GIT_CONFIG_COUNT', '1')
    def fake_git(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1 if 'config' in argv else 0,
                                           stdout='' if 'config' in argv else '.git\n', stderr='')
    runner = Mock(side_effect=fake_git)
    monkeypatch.setattr(subprocess, 'run', runner)
    monkeypatch.setattr('shutil.which', lambda name, **kwargs: '/mock/' + name)
    core.run_command(['python', '-m', 'pytest'], str(tmp_path))
    projects.git(tmp_path, 'status', '--porcelain')
    repository_lock.identity(tmp_path)
    assert sum('config' not in call.args[0] for call in runner.call_args_list) == 3
    for call in runner.call_args_list:
        env = call.kwargs['env']
        assert env.get('SENTINEL_SECRET') is None and env.get('CODEX_HOME') is None and env.get('GIT_CONFIG_COUNT') is None


@pytest.mark.parametrize('scope', ['runner', 'tests', 'git'])
def test_adapter_cannot_use_internal_privileged_scope(scope):
    from pydantic import ValidationError
    from orchestrator.providers.registry import ProviderRegistry
    with pytest.raises(EnvironmentPolicyError, match='Internal'):
        with environment_scope(scope):
            raise AssertionError('Must not enter privileged scope')
    with pytest.raises(ValidationError, match='Internal'):
        CapabilityManifest(adapter=scope, kind='agent_runtime', capabilities={'text'},
            permission_modes=['read_only'], auth_modes=['none'], billing_mode='local', usage_source='none', verified=False)
    with pytest.raises(ValueError, match='internal'):
        ProviderRegistry(enabled_entry_points=[scope])


def test_mismatched_runtime_identity_cannot_select_another_environment(monkeypatch):
    monkeypatch.setenv('ORCH_DB', '/private/db')
    monkeypatch.setenv('HTTP_PROXY', 'private-proxy-value')
    class Misidentified(CommandRuntime):
        provider = 'runner'
        manifest = CapabilityManifest(adapter='fake_cli', kind='agent_runtime', capabilities={'text'},
            permission_modes=['read_only'], auth_modes=['none'], billing_mode='local', usage_source='none', verified=False)
    with environment_config({'claude_code': ['HTTP_PROXY']}):
        with pytest.raises(ValueError, match='must match'):
            Misidentified(Mock())


@pytest.mark.parametrize('invalid', [[], False, '', '{"tests":["CONFIG_DIR"]}'])
def test_invalid_saved_policy_is_not_silently_treated_as_default(invalid):
    from orchestrator.policy.env import snapshot_allowlist
    with pytest.raises(EnvironmentPolicyError, match='saved'):
        snapshot_allowlist({'environment_allowlist': invalid})


def test_filtered_descendant_identifies_group_after_runner_dies(monkeypatch, tmp_path):
    import time
    from orchestrator.execution_manager import boot_id, process_identity
    from orchestrator.worker import clean_group, group_members
    pidfile, release = tmp_path / 'agent-pid', tmp_path / 'release-orphan'
    proof = 'proof-for-filtered-descendant'
    agent_code = (f'import os,time; from pathlib import Path\nPath({str(pidfile)!r}).write_text(str(os.getpid()))\n'
                  f'while not Path({str(release)!r}).exists(): time.sleep(.02)\n')
    leader = tmp_path / 'leader.py'
    root = str(Path(core.__file__).resolve().parent.parent)
    leader.write_text(f'import sys\nsys.path.insert(0, {root!r})\nfrom orchestrator.core import run_command\n'
                      f'run_command([sys.executable, "-c", {agent_code!r}], {str(tmp_path)!r})\n')
    env = safe_env('runner')
    env['ORCH_DISPATCH_TOKEN'] = proof
    parent = subprocess.Popen([sys.executable, str(leader)], env=env, start_new_session=True,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    row = dict(pid=parent.pid, process_start=process_identity(parent.pid)['start'],
               boot_id=boot_id(), dispatch_token=proof)
    try:
        deadline = time.monotonic() + 5
        while not pidfile.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert pidfile.exists()
        parent.kill()
        parent.wait(timeout=5)
        assert clean_group(row)
        assert not group_members(parent.pid)
    finally:
        release.touch()
        if parent.poll() is None:
            parent.kill()
        parent.wait(timeout=5)
        clean_group(row)
