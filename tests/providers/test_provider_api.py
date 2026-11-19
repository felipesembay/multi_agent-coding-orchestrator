"""Local-only provider catalog; plugin activation never comes from HTTP input."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from orchestrator.api import app
from orchestrator.providers import registry
from orchestrator.providers.base import CapabilityManifest, ProbeResult


class FakeRuntime:
    manifest = CapabilityManifest(
        adapter='fake_runtime', kind='agent_runtime', capabilities={'text'},
        permission_modes=['read_only'], auth_modes=['none'], billing_mode='local',
        usage_source='none', verified=False,
    )

    def probe(self):
        return ProbeResult()

    def invoke(self, request):
        raise AssertionError('No invocation while listing')


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr('orchestrator.providers.base.shutil.which', lambda name: '/private/bin/' + name)
    monkeypatch.setattr('subprocess.run', Mock(side_effect=AssertionError('No real CLIs')))
    monkeypatch.setenv('PRIVATE_API_KEY', 'sentinel-private-key')
    with TestClient(app, base_url='http://127.0.0.1:8765', client=('127.0.0.1', 50000)) as client:
        client.headers['X-Orchestrator-CSRF'] = client.get('/session').json()['csrf_token']
        yield client


def test_provider_api_lists_safe_manifest_and_probe(client):
    response = client.get('/providers')
    assert response.status_code == 200
    assert {row['adapter'] for row in response.json()} == {'claude_code', 'codex_cli', 'antigravity', 'openrouter'}
    for row in response.json():
        assert row['manifest']['verified'] is False
        assert row['probe']['version'] is None
        assert row['probe']['credential_present'] is None
    assert 'sentinel-private-key' not in response.text
    assert '/private/bin/' not in response.text
    assert response.headers['cache-control'] == 'no-store'


def test_enabled_fake_plugin_appears_without_core_changes(client, monkeypatch):
    plugin = SimpleNamespace(name='fake_runtime', load=Mock(return_value=FakeRuntime))
    monkeypatch.setattr(registry.metadata, 'entry_points', lambda: {'orchestrator.providers': [plugin]})
    app.dependency_overrides[registry.get_provider_registry] = lambda: registry.ProviderRegistry(enabled_entry_points=['fake_runtime'])
    try:
        response = client.get('/providers')
        assert response.status_code == 200
        assert any(row['adapter'] == 'fake_runtime' and row['source'] == 'entry_point' for row in response.json())
        plugin.load.assert_called_once_with()
    finally:
        app.dependency_overrides.pop(registry.get_provider_registry)


def test_http_parameters_do_not_enable_plugins(client, monkeypatch):
    plugin = SimpleNamespace(name='fake_runtime', load=Mock(return_value=FakeRuntime))
    monkeypatch.setattr(registry.metadata, 'entry_points', lambda: {'orchestrator.providers': [plugin]})
    response = client.get('/providers?enabled_entry_points=fake_runtime')
    assert response.status_code == 200
    assert len(response.json()) == 4
    plugin.load.assert_not_called()


@pytest.mark.parametrize('headers', [{'Host': 'evil.example'}, {'Origin': 'https://evil.example'}, {'Sec-Fetch-Site': 'cross-site'}])
def test_provider_route_rejects_untrusted_browser_request(client, headers):
    assert client.get('/providers', headers=headers).status_code == 403


def test_provider_route_rejects_remote_peer():
    with TestClient(app, base_url='http://127.0.0.1:8765', client=('192.0.2.1', 50000)) as client:
        assert client.get('/providers').status_code == 403
