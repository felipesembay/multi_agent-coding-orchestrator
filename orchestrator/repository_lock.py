"""Advisory repository lock shared by CLI and managed executions (Linux)."""
import fcntl
import os
import subprocess
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

lock_fd = ContextVar('orchestrator_repository_lock_fd', default=None)


def identity(repo):
    result = subprocess.run(
        ['git', '-c', 'core.fsmonitor=false', 'rev-parse', '--git-common-dir'],
        cwd=str(repo), capture_output=True, text=True, timeout=15, check=False,
        env={**{k: v for k, v in os.environ.items() if not k.startswith('GIT_')},
             'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull},
    )
    if result.returncode:
        raise ValueError('Repositório Git inválido')
    path = Path(result.stdout.strip())
    return str((Path(repo) / path).resolve() if not path.is_absolute() else path.resolve())


@contextmanager
def repository_lock(repo):
    common = identity(repo)
    fd = os.open(str(Path(common) / 'orchestrator-execution.lock'),
                 os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    token = None
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Já existe uma execução usando este repositório.') from exc
        token = lock_fd.set(fd)
        yield common
    finally:
        if token is not None:
            lock_fd.reset(token)
        os.close(fd)
