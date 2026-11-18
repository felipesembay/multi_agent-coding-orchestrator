"""Advisory repository lock shared by CLI and managed executions (Linux)."""
import fcntl
import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from .policy.env import safe_env
from .policy.git import run_git

lock_fd = ContextVar('orchestrator_repository_lock_fd', default=None)


def identity(repo):
    result = run_git(['git', 'rev-parse', '--git-common-dir'],
                     cwd=str(repo), timeout=15, env=safe_env('git'))
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
