"""Global local boundary: no route bypass, content leak, or bearer bootstrap."""
import json

import pytest
from fastapi.testclient import TestClient

from orchestrator.api import app
from orchestrator import local_security

ROUTES = ['/health', '/session', '/runs', '/runs/missing', '/runs/missing/events',
          '/overview', '/settings', '/providers', '/projects', '/project-policy',
          '/openapi.json', '/docs', '/redoc', '/missing']
PROTECTED = [path for path in ROUTES if path not in ('/health', '/session')]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('ORCH_DB', str(tmp_path / 'events.db'))
    monkeypatch.delenv('ORCH_ALLOWED_ORIGINS', raising=False)
    with TestClient(app, base_url='http://127.0.0.1:8765', client=('127.0.0.1', 50000)) as client:
        yield client


@pytest.mark.parametrize('path', ROUTES)
@pytest.mark.parametrize('headers', [{'Host': 'evil.example'}, {'Origin': 'https://evil.example'},
                                    {'Sec-Fetch-Site': 'cross-site'}])
def test_every_route_enforces_browser_boundary(client, path, headers):
    assert client.get(path, headers=headers).status_code == 403


@pytest.mark.parametrize('path', ROUTES)
def test_every_route_rejects_remote_peer(path):
    with TestClient(app, base_url='http://127.0.0.1:8765', client=('192.0.2.1', 50000)) as remote:
        assert remote.get(path, headers={'X-Forwarded-For': '127.0.0.1'}).status_code == 403


@pytest.mark.parametrize('path', PROTECTED)
def test_reads_require_token_even_on_loopback(client, path):
    assert client.get(path).status_code == 403


@pytest.mark.parametrize('host', ['localhost.evil.example', 'localhost:bad', 'localhost:',
                                 '127.0.0.1:0', '127.0.0.1:65536', 'user@localhost',
                                 'localhost/path', 'localhost#fragment', ' localhost', '::1'])
def test_ambiguous_host_is_rejected(client, host):
    assert client.get('/health', headers={'Host': host}).status_code == 403


def test_duplicate_host_is_rejected(client):
    assert client.get('/health', headers=[('Host', '127.0.0.1'), ('Host', 'evil.example')]).status_code == 403


@pytest.mark.parametrize('host', ['localhost', 'localhost:8765', '127.0.0.1', '[::1]:8765'])
def test_valid_local_hosts_can_bootstrap(client, host):
    assert client.get('/health', headers={'Host': host}).status_code == 200
    assert client.get('/session', headers={'Host': host}).status_code == 200


def test_bootstrap_only_exposes_csrf_and_all_responses_have_security_headers(client):
    response = client.get('/session')
    assert set(response.json()) == {'csrf_token'}
    assert response.json()['csrf_token'] == local_security.CSRF_TOKEN
    assert local_security.API_TOKEN not in response.text
    for response in [response, client.get('/health'), client.get('/runs'),
                     client.get('/health', headers={'Host': 'evil.example'})]:
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers['cross-origin-resource-policy'] == 'same-origin'


def test_browser_token_authenticates_reads_and_writes(client):
    token = client.get('/session').json()['csrf_token']
    headers = {'X-Orchestrator-CSRF': token}
    assert client.get('/runs', headers=headers).json() == []
    assert client.get('/settings', headers=headers).status_code == 200
    assert client.post('/runs', json={}, headers=headers).status_code == 403  # Writes need trusted Origin.
    assert client.post('/runs', json={}, headers={**headers, 'Origin': 'http://127.0.0.1:5173'}).status_code == 405


def test_bearer_authenticates_native_client_without_origin(client):
    headers = {'Authorization': 'Bearer ' + local_security.API_TOKEN}
    assert client.get('/runs', headers=headers).status_code == 200
    assert client.post('/runs', json={}, headers=headers).status_code == 405
    assert client.get('/session', headers=headers).json() == {'csrf_token': local_security.CSRF_TOKEN}
    assert client.get('/runs', headers={**headers, 'Origin': 'https://evil.example'}).status_code == 403


def test_bearer_configuration_is_in_memory_and_not_disclosed(client):
    configured = 'configured-native-token-' + 'x' * 32
    app.state.api_token = configured
    try:
        assert client.get('/runs', headers={'Authorization': 'Bearer ' + configured}).status_code == 200
        assert client.get('/runs', headers={'Authorization': 'Bearer ' + local_security.API_TOKEN}).status_code == 403
        assert configured not in client.get('/session').text
        response = client.get('/settings', headers={'Authorization': 'Bearer ' + configured})
        assert configured not in response.text
    finally:
        del app.state.api_token


@pytest.mark.parametrize('headers', [
    {'X-Orchestrator-CSRF': 'wrong'}, {'Authorization': 'Bearer wrong'},
    {'Authorization': 'Basic ignored'}, {b'X-Orchestrator-CSRF': b'\xe9'},
])
def test_invalid_credentials_fail_without_leaking_values(client, headers):
    response = client.get('/settings', headers=headers)
    assert response.status_code == 403
    assert local_security.CSRF_TOKEN not in response.text
    assert local_security.API_TOKEN not in response.text


def test_explicit_bad_bearer_cannot_fall_back_to_good_csrf(client):
    assert client.get('/runs', headers={'Authorization': 'Bearer wrong',
        'X-Orchestrator-CSRF': local_security.CSRF_TOKEN}).status_code == 403


def test_rotated_csrf_rejects_stale_read_token(client, monkeypatch):
    old = client.get('/session').json()['csrf_token']
    monkeypatch.setattr(local_security, 'CSRF_TOKEN', 'rotated-browser-token')
    assert client.get('/runs', headers={'X-Orchestrator-CSRF': old}).status_code == 403
    new = client.get('/session').json()['csrf_token']
    assert new == 'rotated-browser-token'
    assert client.get('/runs', headers={'X-Orchestrator-CSRF': new}).status_code == 200


def test_body_limit_applies_to_bearer_and_csrf(client):
    for headers in [{'Authorization': 'Bearer ' + local_security.API_TOKEN},
                    {'X-Orchestrator-CSRF': local_security.CSRF_TOKEN, 'Origin': 'http://localhost:5173'}]:
        response = client.post('/projects/preview', content=json.dumps({'padding': 'x' * 150001}),
                              headers={**headers, 'Content-Type': 'application/json'})
        assert response.status_code == 413
