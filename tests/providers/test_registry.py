"""Provider discovery never invokes agents or imports unapproved plugins."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from orchestrator.providers import registry
from orchestrator.providers.base import Capability, CapabilityManifest, ProbeResult


BUILTINS = {'claude_code', 'codex_cli', 'antigravity'}


class FakeRuntime:
    manifest = CapabilityManifest(
        adapter='fake_runtime', kind='agent_runtime', capabilities={Capability.TEXT},
        permission_modes=['read_only'], auth_modes=['none'], billing_mode='local',
        usage_source='none', verified=False,
    )

    def probe(self):
        return ProbeResult(executable_found=None)

    def invoke(self, request):
        raise AssertionError('Listing must never invoke an agent')


def entry(name='fake_runtime', factory=FakeRuntime):
    return SimpleNamespace(name=name, load=Mock(return_value=factory))


@pytest.fixture
def discovery(monkeypatch):
    discover = Mock(return_value={'orchestrator.providers': []})
    monkeypatch.setattr(registry.metadata, 'entry_points', discover)
    monkeypatch.setattr('orchestrator.providers.base.shutil.which', lambda name: '/private/' + name)
    return discover


def test_builtins_only_and_no_discovery_without_opt_in(discovery):
    catalog = registry.ProviderRegistry()
    rows = catalog.list()
    assert {row.adapter for row in rows} == BUILTINS
    discovery.assert_not_called()
    for row in rows:
        assert row.source == 'builtin'
        assert row.manifest.adapter == row.adapter
        assert row.manifest.verified is False
        assert row.manifest.usage_source == 'none'
        assert row.manifest.billing_mode == 'unknown'
        assert row.probe.executable_found is True
        assert row.probe.version is None
        assert row.probe.credential_present is None
        assert '/private/' not in row.model_dump_json()
        assert Capability.USAGE_METRICS not in row.manifest.capabilities
        assert Capability.STRUCTURED_OUTPUT not in row.manifest.capabilities
    assert catalog.get('codex_cli').manifest.permission_modes == ['read_only', 'workspace_write']
    assert catalog.get('claude_code').manifest.permission_modes == ['read_only', 'workspace_write']
    assert Capability.CODE_EDIT in catalog.get('codex_cli').manifest.capabilities
    assert Capability.CODE_EXEC in catalog.get('codex_cli').manifest.capabilities
    with pytest.raises(KeyError):
        catalog.get('not_installed')


def test_probe_is_passive_and_does_not_infer_authentication(discovery, monkeypatch):
    monkeypatch.setattr('orchestrator.providers.base.shutil.which', lambda name: None)
    monkeypatch.setattr('subprocess.run', Mock(side_effect=AssertionError('No CLI probes')))
    rows = registry.ProviderRegistry().list()
    assert all(row.probe.executable_found is False for row in rows)
    assert all(row.probe.credential_present is None and row.probe.version is None for row in rows)


def test_only_enabled_entry_point_is_loaded(discovery):
    enabled, disabled = entry(), entry('disabled_runtime')
    discovery.return_value = {'orchestrator.providers': [disabled, enabled]}
    catalog = registry.ProviderRegistry(enabled_entry_points={'fake_runtime'})
    assert {row.adapter for row in catalog.list()} == BUILTINS | {'fake_runtime'}
    assert isinstance(catalog.get('fake_runtime'), FakeRuntime)
    enabled.load.assert_called_once_with()
    disabled.load.assert_not_called()
    catalog.list()
    enabled.load.assert_called_once_with()  # No repeat import/factory per listing.


def test_selectable_entry_points_are_supported(discovery):
    plugin = entry()
    discovery.return_value = SimpleNamespace(select=Mock(return_value=[plugin]))
    rows = registry.ProviderRegistry(enabled_entry_points=['fake_runtime']).list()
    assert any(row.adapter == 'fake_runtime' and row.manifest is not None for row in rows)
    discovery.return_value.select.assert_called_once_with(group='orchestrator.providers')


def test_installed_plugin_cannot_shadow_builtin(discovery):
    plugin = entry('claude_code')
    discovery.return_value = {'orchestrator.providers': [plugin]}
    with pytest.raises(ValueError, match='built-in'):
        registry.ProviderRegistry(enabled_entry_points=['claude_code'])
    plugin.load.assert_not_called()


def test_duplicate_entry_points_are_rejected_before_import(discovery):
    one, two = entry(), entry()
    discovery.return_value = {'orchestrator.providers': [one, two]}
    row = next(row for row in registry.ProviderRegistry(enabled_entry_points=['fake_runtime']).list()
               if row.adapter == 'fake_runtime')
    assert row.manifest is None
    assert row.probe.error_code == 'duplicate_entry_point'
    one.load.assert_not_called()
    two.load.assert_not_called()


@pytest.mark.parametrize('problem,code', [('missing', 'entry_point_missing'), ('load', 'load_failed'), ('invalid', 'invalid_provider'), ('probe', 'probe_failed')])
def test_broken_plugin_isolated_and_errors_are_redacted(discovery, problem, code):
    plugin = entry()
    if problem == 'missing':
        discovery.return_value = {'orchestrator.providers': []}
    else:
        discovery.return_value = {'orchestrator.providers': [plugin]}
    if problem == 'load':
        plugin.load.side_effect = RuntimeError('secret-token from plugin loader')
    if problem == 'invalid':
        plugin.load.return_value = lambda: SimpleNamespace(manifest={'adapter': 'secret-token'})
    if problem == 'probe':
        class BadProbe(FakeRuntime):
            def probe(self):
                raise RuntimeError('secret-token from probe')
        plugin.load.return_value = BadProbe
    rows = registry.ProviderRegistry(enabled_entry_points=['fake_runtime']).list()
    assert len(rows) == 4
    row = next(row for row in rows if row.adapter == 'fake_runtime')
    assert row.probe.error_code == code
    assert 'secret-token' not in row.model_dump_json()
    assert all(row.manifest is not None for row in rows if row.adapter in BUILTINS)


def test_plugin_cannot_misidentify_its_adapter(discovery):
    class Misnamed(FakeRuntime):
        manifest = FakeRuntime.manifest.model_copy(update={'adapter': 'antigravity'})
    discovery.return_value = {'orchestrator.providers': [entry(factory=Misnamed)]}
    row = next(row for row in registry.ProviderRegistry(enabled_entry_points=['fake_runtime']).list()
               if row.adapter == 'fake_runtime')
    assert row.manifest is None
    assert row.probe.error_code == 'invalid_provider'


def test_manifest_cannot_be_changed_through_listing(discovery):
    catalog = registry.ProviderRegistry()
    listing = next(row for row in catalog.list() if row.adapter == 'codex_cli')
    listing.manifest.permission_modes.clear()
    assert catalog.get('codex_cli').manifest.permission_modes == ['read_only', 'workspace_write']


def test_injected_runner_and_observer_make_builtin_usable_without_core(discovery):
    from orchestrator.providers.base import InvocationRequest
    runner, observed = Mock(return_value='answer'), []
    provider = registry.ProviderRegistry(runner=runner, observer=observed.append).get('claude_code')
    result = provider.invoke(InvocationRequest(prompt='task', cwd='/tmp/tree', permission='workspace_write'))
    assert result.text == 'answer'
    assert runner.call_count == 1
    assert runner.call_args.args == (['claude', '-p', '--permission-mode', 'acceptEdits', '--disallowedTools', 'Bash', 'task'], '/tmp/tree', 600)
    assert isinstance(runner.call_args.kwargs['env'], dict)
    assert len(observed) == 1
    assert observed[0].provider == 'claude_code'


def test_discovery_failure_does_not_break_builtins(discovery):
    discovery.side_effect = RuntimeError('secret-discovery')
    rows = registry.ProviderRegistry(enabled_entry_points=['fake_runtime']).list()
    assert len(rows) == 4
    assert next(row for row in rows if row.adapter == 'fake_runtime').probe.error_code == 'load_failed'
    assert 'secret-discovery' not in ''.join(row.model_dump_json() for row in rows)


def test_invalid_probe_payload_is_not_returned(discovery):
    class BadProbe(FakeRuntime):
        def probe(self):
            return {'version': 'secret-token', 'environment': {'API_KEY': 'secret-token'}}
    discovery.return_value = {'orchestrator.providers': [entry(factory=BadProbe)]}
    row = next(row for row in registry.ProviderRegistry(enabled_entry_points=['fake_runtime']).list()
               if row.adapter == 'fake_runtime')
    assert row.manifest is not None
    assert row.probe.error_code == 'probe_failed'
    assert 'secret-token' not in row.model_dump_json()


def test_model_provider_plugin_is_cataloged_separately(discovery):
    class FakeModel:
        manifest = FakeRuntime.manifest.model_copy(update={'adapter': 'fake_model', 'kind': 'model_provider'})
        def probe(self):
            return ProbeResult(credential_present=False)
        def generate(self, request, context):
            raise AssertionError('No model invocation')
        def list_models(self):
            raise AssertionError('No model catalog network calls during discovery')
    discovery.return_value = {'orchestrator.providers': [entry(name='fake_model', factory=FakeModel)]}
    row = next(row for row in registry.ProviderRegistry(enabled_entry_points=['fake_model']).list()
               if row.adapter == 'fake_model')
    assert row.manifest.kind == 'model_provider'
    assert row.probe.executable_found is None
    assert row.probe.credential_present is False


def test_builtin_probe_failure_does_not_leak_filesystem_details(discovery, monkeypatch):
    monkeypatch.setattr('orchestrator.providers.base.shutil.which', Mock(side_effect=OSError('/private/secret-path')))
    rows = registry.ProviderRegistry().list()
    assert len(rows) == 3
    assert all(row.probe.error_code == 'probe_failed' and row.manifest is not None for row in rows)
    assert '/private/secret-path' not in ''.join(row.model_dump_json() for row in rows)
