import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from orchestrator.api import app
from orchestrator.project_store import connection
from orchestrator import projects


@pytest.fixture
def client(tmp_path, monkeypatch):
    root = tmp_path / 'allowed'
    root.mkdir()
    monkeypatch.setenv('ORCH_DB', str(tmp_path / 'events.db'))
    monkeypatch.setenv('ORCH_ALLOWED_ROOTS', str(root))
    monkeypatch.delenv('ORCH_ALLOWED_ORIGINS', raising=False)
    with TestClient(app, base_url='http://127.0.0.1:8765', client=('127.0.0.1', 50000)) as client:
        token = client.get('/session').json()['csrf_token']
        client.headers.update({'Origin': 'http://127.0.0.1:5173', 'X-Orchestrator-CSRF': token})
        client.root = root
        yield client


def input_data(client, **changes):
    return dict(name='Sistema de Recomendação de Filmes', description='Recomenda filmes',
                objectives='API e testes', repo_path=str(client.root / 'movies'), mode='create', **changes)


def create(client):
    preview = client.post('/projects/preview', json=input_data(client))
    assert preview.status_code == 200, preview.text
    response = client.post('/projects', json={'preview_token': preview.json()['preview_token'], 'confirmed': True})
    assert response.status_code == 201, response.text
    return response.json()


def git(path, *args):
    return subprocess.check_output(['git', *args], cwd=path, text=True).strip()


def test_new_project_confirmation_and_persistence(client):
    payload = input_data(client)
    result = client.post('/projects/preview', json=payload)
    assert result.status_code == 200
    assert not (client.root / 'movies').exists()
    assert client.post('/projects', json={'preview_token': result.json()['preview_token'], 'confirmed': False}).status_code == 422
    response = client.post('/projects', json={'preview_token': result.json()['preview_token'], 'confirmed': True})
    assert response.status_code == 201, response.text
    project = response.json()
    path = client.root / 'movies'
    assert git(path, 'rev-parse', '--verify', 'HEAD')
    assert git(path, 'status', '--porcelain') == ''
    assert 'Sistema de Recomendação de Filmes' in (path / 'README.md').read_text()
    assert client.get('/projects').json()[0]['id'] == project['id']
    # Fresh client/connection reads the same persisted project.
    with TestClient(app, base_url='http://localhost:8765', client=('127.0.0.1', 50000)) as restarted:
        assert restarted.get('/projects/' + project['id']).json()['name'] == payload['name']
    assert client.post('/projects', json={'preview_token': result.json()['preview_token'], 'confirmed': True}).json()['id'] == project['id']
    assert len(client.get('/projects').json()) == 1
    with connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM platform_audit WHERE action=?', ('project.created',)).fetchone()[0] == 1
        assert conn.execute('SELECT version FROM platform_migrations').fetchone()[0] == 1


def test_existing_repository_not_modified(client):
    path = client.root / 'existing'
    path.mkdir()
    git(path, 'init')
    (path / 'existing.txt').write_text('User content')
    before = git(path, 'status', '--porcelain')
    payload = input_data(client)
    payload.update(mode='existing', repo_path=str(path))
    preview = client.post('/projects/preview', json=payload)
    assert preview.status_code == 200, preview.text
    response = client.post('/projects', json={'preview_token': preview.json()['preview_token'], 'confirmed': True})
    assert response.status_code == 201
    assert git(path, 'status', '--porcelain') == before
    assert (path / 'existing.txt').read_text() == 'User content'


def test_request_edit_archive_and_validation(client):
    project = create(client)
    url = '/projects/' + project['id']
    content = 'Crie uma API FastAPI com PostgreSQL, testes e documentação.'
    response = client.post(url + '/requests', json={'title': 'Criar API', 'content': content})
    assert response.status_code == 201
    assert client.get(url + '/requests').json()[0]['content'] == content
    assert client.get('/projects').json()[0]['request_count'] == 1
    update = dict(name='Filmes v2', description='Descrição nova', objectives='Objetivos novos', state='archived')
    assert client.patch(url, json=update).json()['name'] == 'Filmes v2'
    assert client.post(url + '/requests', json={'title': 'Novo', 'content': 'Texto'}).status_code == 409
    update['state'] = 'active'
    client.patch(url, json=update)
    assert client.post(url + '/requests', json={'title': '  ', 'content': 'Texto'}).status_code == 422
    assert client.post(url + '/requests', json={'title': 'Novo', 'content': 'a' * 100001}).status_code == 422
    assert client.post('/projects/missing/requests', json={'title': 'Novo', 'content': 'Texto'}).status_code == 404
    assert client.get('/projects/missing').status_code == 404


@pytest.mark.parametrize('headers', [
    {'Origin': 'http://evil.invalid'},
    {'Host': 'evil.invalid'},
    {'X-Orchestrator-CSRF': 'wrong'},
    {'Origin': 'null'},
    {'Sec-Fetch-Site': 'cross-site'},
])
def test_mutation_security(client, headers):
    response = client.post('/projects/preview', json=input_data(client), headers=headers)
    assert response.status_code == 403
    assert not (client.root / 'movies').exists()


def test_missing_origin_token_and_cross_origin_reads(client):
    client.headers.pop('Origin')
    assert client.post('/projects/preview', json=input_data(client)).status_code == 403
    assert client.get('/session', headers={'Origin': 'https://evil.invalid'}).status_code == 403
    assert client.get('/session', headers={'Host': 'localhost.evil.invalid'}).status_code == 403
    assert client.get('/session', headers={'Host': 'localhost:bad'}).status_code == 403
    assert client.get('/session', headers={'Host': '127.0.0.1:8765'}).headers['cache-control'] == 'no-store'


def test_paths_and_expired_preview(client, tmp_path, monkeypatch):
    for path in [str(tmp_path / 'outside'), str(client.root / '..' / 'escape'), str(client.root), 'relative']:
        payload = input_data(client)
        payload['repo_path'] = path
        assert client.post('/projects/preview', json=payload).status_code in (400, 403)
    (client.root / 'link').symlink_to(tmp_path, target_is_directory=True)
    payload = input_data(client)
    payload['repo_path'] = str(client.root / 'link' / 'escape')
    assert client.post('/projects/preview', json=payload).status_code in (400, 403)
    preview = client.post('/projects/preview', json=input_data(client)).json()
    with connection() as conn:
        conn.execute('UPDATE project_previews SET expires_at=?', (time.time() - 1,))
        conn.commit()
    assert client.post('/projects', json={'preview_token': preview['preview_token'], 'confirmed': True}).status_code == 409
    monkeypatch.delenv('ORCH_ALLOWED_ROOTS')
    assert client.get('/project-policy').json()['roots'] == []
    assert client.post('/projects/preview', json=input_data(client)).status_code == 403


def test_revalidate_and_never_overwrite(client):
    preview = client.post('/projects/preview', json=input_data(client)).json()
    path = client.root / 'movies'
    path.mkdir()
    (path / 'precious.txt').write_text('keep')
    response = client.post('/projects', json={'preview_token': preview['preview_token'], 'confirmed': True})
    assert response.status_code == 409
    assert (path / 'precious.txt').read_text() == 'keep'
    assert not (path / '.git').exists()


def test_same_confirmation_is_safe_under_concurrent_calls(client):
    token = client.post('/projects/preview', json=input_data(client)).json()['preview_token']
    confirmation = projects.ProjectConfirmation(preview_token=token, confirmed=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: projects.create(confirmation), range(2)))
    assert results[0]['id'] == results[1]['id']
    assert len(client.get('/projects').json()) == 1


def test_linked_git_directory_must_also_be_authorized(client, tmp_path):
    outside = tmp_path / 'private-git'
    outside.mkdir()
    git(outside, 'init')
    worktree = client.root / 'linked'
    worktree.mkdir()
    (worktree / '.git').write_text('gitdir: ' + str(outside / '.git'))
    payload = input_data(client)
    payload.update(mode='existing', repo_path=str(worktree))
    assert client.post('/projects/preview', json=payload).status_code == 403


def test_project_history_matches_repository_without_invented_task_links(client):
    project = create(client)
    from orchestrator.core import db, db_path
    import json
    with db(db_path()) as conn:
        conn.execute('INSERT INTO events(run_id,stage,payload) VALUES(?,?,?)', ('legacy', 'started', json.dumps({'repo': project['repo_path']})))
        conn.execute('INSERT INTO events(run_id,stage,payload) VALUES(?,?,?)', ('other', 'started', json.dumps({'repo': '/elsewhere'})))
    history = client.get('/projects/' + project['id'] + '/runs').json()
    assert [r['run_id'] for r in history] == ['legacy']
    assert client.get('/projects/' + project['id'] + '/requests').json() == []


def test_git_environment_is_not_inherited(client, tmp_path, monkeypatch):
    protected = tmp_path / 'do-not-touch'
    protected.mkdir()
    monkeypatch.setenv('GIT_DIR', str(protected))
    monkeypatch.setenv('GIT_WORK_TREE', str(protected))
    create(client)
    assert list(protected.iterdir()) == []


def test_content_type_and_size_limits(client):
    assert client.post('/projects/preview', content='text', headers={'Content-Type': 'text/plain'}).status_code == 415
    assert client.post('/projects/preview', content='x' * 150001, headers={'Content-Type': 'application/json'}).status_code == 413


def test_remote_client_cannot_spoof_local_headers(client):
    with TestClient(app, base_url='http://127.0.0.1:8765', client=('192.0.2.10', 50000)) as remote:
        assert remote.get('/session').status_code == 403
        assert remote.post('/projects/preview', json=input_data(client), headers=dict(client.headers)).status_code == 403


def test_exact_repository_allowlist(client, monkeypatch):
    path = client.root / 'exact'
    path.mkdir()
    git(path, 'init')
    monkeypatch.setenv('ORCH_ALLOWED_ROOTS', str(path))
    payload = input_data(client)
    payload.update(mode='existing', repo_path=str(path))
    assert client.post('/projects/preview', json=payload).status_code == 200


def test_symlink_loop_is_a_validation_error(client):
    path = client.root / 'loop'
    path.symlink_to(path)
    payload = input_data(client)
    payload['repo_path'] = str(path)
    assert client.post('/projects/preview', json=payload).status_code == 422


def test_failed_git_creation_is_audited_without_deleting_files(client, monkeypatch):
    preview = client.post('/projects/preview', json=input_data(client)).json()
    real_git = projects.git
    def fail_commit(path, *args, **kwargs):
        if args[0] == 'commit':
            raise projects.ProjectError('Falha no commit inicial.', 422)
        return real_git(path, *args, **kwargs)
    monkeypatch.setattr(projects, 'git', fail_commit)
    assert client.post('/projects', json={'preview_token': preview['preview_token'], 'confirmed': True}).status_code == 422
    assert (client.root / 'movies' / 'README.md').exists()
    assert client.get('/projects').json() == []
    with connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM platform_audit WHERE action='project.creation_failed'").fetchone()[0] == 1


def test_non_ascii_token_is_rejected_not_a_server_error(client):
    assert client.post('/projects/preview', json=input_data(client), headers={b'X-Orchestrator-CSRF': b'\xe9'}).status_code == 403


def test_git_missing_fails_before_creating_directory(client, monkeypatch):
    monkeypatch.setattr(projects.shutil, 'which', lambda _: None)
    assert client.get('/project-policy').json()['git_available'] is False
    assert client.post('/projects/preview', json=input_data(client)).status_code == 503
    assert not (client.root / 'movies').exists()
