"""Project catalog and explicit, previewed repository creation. Never runs agents."""
import json
import os
import secrets
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .project_store import connection


class ProjectError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=5000)
    objectives: str = Field(default='', max_length=10000)
    repo_path: str = Field(min_length=1, max_length=4096)
    mode: Literal['existing', 'create']

    @field_validator('repo_path')
    @classmethod
    def valid_path_text(cls, value):
        if '\x00' in value or '\n' in value or '\r' in value:
            raise ValueError('Caminho inválido')
        return value


class ProjectConfirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preview_token: str = Field(min_length=20, max_length=100)
    confirmed: Literal[True]


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=5000)
    objectives: str = Field(default='', max_length=10000)
    state: Literal['active', 'archived']


class RequestInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=100000)


def roots():
    configured = os.getenv('ORCH_ALLOWED_ROOTS', '')
    result = []
    for item in configured.split(os.pathsep):
        if item.strip():
            root = Path(item.strip()).expanduser().resolve()
            if root not in result:
                result.append(root)
    return result


def policy():
    return dict(roots=[dict(path=str(p), available=p.is_dir()) for p in roots()],
                git_available=shutil.which('git') is not None,
                preview_ttl_seconds=600)


def authorized_path(value, allow_root=False):
    path = Path(value).expanduser()
    if not path.is_absolute() or '..' in path.parts:
        raise ProjectError('Informe um caminho absoluto, sem segmentos "..".')
    try:
        canonical = path.resolve()
    except (OSError, RuntimeError) as exc:
        raise ProjectError('Caminho inválido ou inacessível.', 422) from exc
    for root in roots():
        try:
            relative = path.relative_to(root)
            canonical.relative_to(root)
        except ValueError:
            continue
        if not relative.parts and not allow_root:
            raise ProjectError('Escolha um diretório dentro da raiz autorizada, não a própria raiz.')
        candidate = root
        for part in relative.parts:
            if part.startswith('.'):
                raise ProjectError('Diretórios ocultos não podem ser usados como projetos.')
            candidate /= part
            if candidate.is_symlink():
                raise ProjectError('Links simbólicos não são permitidos no caminho do projeto.')
        if not root.is_dir():
            raise ProjectError('A raiz autorizada não existe. Crie-a antes de continuar.')
        return canonical, root
    raise ProjectError('Diretório não autorizado. Configure ORCH_ALLOWED_ROOTS no processo que executa a operação (API ou worker).', 403)


def git(path, *args, directory_fd=None):
    if shutil.which('git') is None:
        raise ProjectError('Git não está disponível no servidor.', 503)
    argv = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
            '-c', 'commit.gpgsign=false', '-c', 'user.name=Orchestrator Local',
            '-c', 'user.email=orchestrator@local.invalid', *args]
    try:
        result = subprocess.run(argv, cwd=str(path), capture_output=True, text=True,
                                timeout=20, check=False,
                                pass_fds=() if directory_fd is None else (directory_fd,),
                                env={**{k: v for k, v in os.environ.items() if not k.startswith('GIT_')},
                                     'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProjectError('Não foi possível concluir a operação Git local.', 422) from exc
    if result.returncode:
        # Do not return raw stderr: local Git configuration can contain sensitive paths.
        raise ProjectError('O diretório não é um repositório Git utilizável para esta operação.', 422)
    return result.stdout.strip()


def validate_input(data):
    if shutil.which('git') is None:
        raise ProjectError('Git não está disponível no servidor.', 503)
    path, root = authorized_path(data.repo_path, allow_root=data.mode == 'existing')
    if data.mode == 'create':
        if path.exists():
            raise ProjectError('O diretório já existe. Use “Registrar repositório existente”.', 409)
        if not path.parent.is_dir():
            raise ProjectError('O diretório pai precisa existir dentro da raiz autorizada.')
    else:
        if not path.is_dir() or not (path / '.git').exists() or (path / '.git').is_symlink():
            raise ProjectError('Selecione a raiz de um repositório Git existente.', 422)
        if Path(git(path, 'rev-parse', '--show-toplevel')).resolve() != path:
            raise ProjectError('Selecione a raiz do repositório, não um subdiretório.', 422)
        common = Path(git(path, 'rev-parse', '--git-common-dir'))
        common = (path / common).resolve() if not common.is_absolute() else common.resolve()
        if not any(common.is_relative_to(allowed) for allowed in roots()):
            raise ProjectError('O diretório Git compartilhado também precisa estar autorizado.', 403)
    return path, root


def parent_identity(path):
    try:
        parent = path.parent.stat()
        return parent.st_dev, parent.st_ino
    except OSError as exc:
        raise ProjectError('Diretório pai inacessível. Verifique as permissões.', 422) from exc


def audit(conn, action, project_id=None, **details):
    conn.execute('INSERT INTO platform_audit(action,project_id,details) VALUES(?,?,?)',
                 (action, project_id, json.dumps(details, ensure_ascii=False)))


def preview(data):
    path, _ = validate_input(data)
    data = data.model_copy(update={'repo_path': str(path)})
    parent_device, parent_inode = parent_identity(path)
    token = secrets.token_urlsafe(32)
    with connection() as conn:
        conn.execute('DELETE FROM project_previews WHERE expires_at<? AND project_id IS NULL', (time.time(),))
        conn.execute('INSERT INTO project_previews(token,payload,parent_device,parent_inode,expires_at) VALUES(?,?,?,?,?)',
                     (token, data.model_dump_json(), parent_device, parent_inode, time.time() + 600))
        audit(conn, 'project.preview', mode=data.mode, path=str(path))
        conn.commit()
    return dict(preview_token=token, project=data.model_dump(),
                actions=['Criar diretório', 'Inicializar Git sem hooks', 'Criar README.md e commit inicial local', 'Cadastrar projeto'] if data.mode == 'create' else ['Associar repositório existente', 'Cadastrar projeto; arquivos e commits existentes não serão alterados'],
                expires_in_seconds=600)


def initialize_repository(path, root, data, parent_identity):
    """Create only one new leaf using no-follow directory descriptors (Linux)."""
    parent_fd = None
    directory_fd = None
    try:
        parent_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for part in path.parent.relative_to(root).parts:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = next_fd
        parent_stat = os.fstat(parent_fd)
        if (parent_stat.st_dev, parent_stat.st_ino) != parent_identity:
            raise ProjectError('O diretório pai mudou. Revise o projeto novamente.', 409)
        os.mkdir(path.name, dir_fd=parent_fd)
        directory_fd = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        fd_path = f'/proc/self/fd/{directory_fd}'
        git(fd_path, 'init', '--template=', directory_fd=directory_fd)
        readme_fd = os.open('README.md', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=directory_fd)
        with os.fdopen(readme_fd, 'w', encoding='utf-8') as stream:
            stream.write(f'# {data.name}\n\n{data.description}\n\n## Objetivos\n\n{data.objectives}\n')
        git(fd_path, 'add', '--', 'README.md', directory_fd=directory_fd)
        git(fd_path, 'commit', '-m', 'Initialize project', directory_fd=directory_fd)
        actual, expected = path.stat(), os.fstat(directory_fd)
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino) or path.resolve() != path:
            raise ProjectError('O caminho mudou durante a criação. Inspecione o diretório antes de tentar novamente.', 409)
    except FileExistsError as exc:
        raise ProjectError('O diretório passou a existir. Nada foi sobrescrito.', 409) from exc
    except OSError as exc:
        raise ProjectError('Falha ao criar o diretório. Verifique permissões e eventuais arquivos criados antes de tentar novamente.', 422) from exc
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
        if parent_fd is not None:
            os.close(parent_fd)


PROJECT_SELECT = '''SELECT p.*, r.path AS repo_path FROM projects p
                    JOIN repositories r ON r.id=p.repository_id'''


def get_project(project_id, conn=None):
    if conn is None:
        with connection() as owned:
            return get_project(project_id, owned)
    row = conn.execute(PROJECT_SELECT + ' WHERE p.id=?', (project_id,)).fetchone()
    if row is None:
        raise ProjectError('Projeto não encontrado.', 404)
    return dict(row)


def create(confirmation):
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM project_previews WHERE token=?', (confirmation.preview_token,)).fetchone()
        if row is None:
            raise ProjectError('Confirmação inválida. Revise o projeto novamente.', 422)
        if row['project_id']:
            return get_project(row['project_id'], conn)
        if row['expires_at'] < time.time():
            raise ProjectError('A confirmação expirou. Revise o projeto novamente.', 409)
        data = ProjectInput.model_validate_json(row['payload'])
        path, root = validate_input(data)
        if parent_identity(path) != (row['parent_device'], row['parent_inode']):
            raise ProjectError('O diretório pai mudou. Revise o projeto novamente.', 409)
        if data.mode == 'create':
            try:
                initialize_repository(path, root, data, (row['parent_device'], row['parent_inode']))
            except ProjectError:
                audit(conn, 'project.creation_failed', path=str(path))
                conn.commit()
                raise
        common = Path(git(path, 'rev-parse', '--git-common-dir'))
        common = (path / common).resolve() if not common.is_absolute() else common.resolve()
        repo_id = 'repo-' + uuid.uuid4().hex
        conn.execute('INSERT OR IGNORE INTO repositories(id,path,git_common_dir) VALUES(?,?,?)', (repo_id, str(path), str(common)))
        repo_id = conn.execute('SELECT id FROM repositories WHERE path=?', (str(path),)).fetchone()['id']
        project_id = 'project-' + uuid.uuid4().hex
        conn.execute('INSERT INTO projects(id,name,description,objectives,repository_id) VALUES(?,?,?,?,?)',
                     (project_id, data.name, data.description, data.objectives, repo_id))
        conn.execute('UPDATE project_previews SET project_id=? WHERE token=?', (project_id, confirmation.preview_token))
        audit(conn, 'project.created', project_id, mode=data.mode, path=str(path))
        conn.commit()
        return get_project(project_id, conn)


def list_projects():
    with connection() as conn:
        rows = conn.execute(PROJECT_SELECT + ''' ORDER BY p.updated_at DESC, p.rowid DESC''').fetchall()
        return [dict(row, request_count=conn.execute('SELECT COUNT(*) FROM project_requests WHERE project_id=?', (row['id'],)).fetchone()[0]) for row in rows]


def update_project(project_id, data):
    with connection() as conn:
        get_project(project_id, conn)
        conn.execute('UPDATE projects SET name=?,description=?,objectives=?,state=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                     (data.name, data.description, data.objectives, data.state, project_id))
        audit(conn, 'project.updated', project_id, state=data.state)
        conn.commit()
        return get_project(project_id, conn)


def requests(project_id):
    with connection() as conn:
        get_project(project_id, conn)
        return [dict(row) for row in conn.execute('SELECT * FROM project_requests WHERE project_id=? ORDER BY rowid DESC', (project_id,))]


def submit_request(project_id, data):
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        project = get_project(project_id, conn)
        if project['state'] != 'active':
            raise ProjectError('Reative o projeto antes de adicionar solicitações.', 409)
        request_id = 'request-' + uuid.uuid4().hex
        conn.execute('INSERT INTO project_requests(id,project_id,title,content) VALUES(?,?,?,?)', (request_id, project_id, data.title, data.content))
        conn.execute('UPDATE projects SET updated_at=CURRENT_TIMESTAMP WHERE id=?', (project_id,))
        audit(conn, 'request.created', project_id, request_id=request_id)
        conn.commit()
        return dict(conn.execute('SELECT * FROM project_requests WHERE id=?', (request_id,)).fetchone())
