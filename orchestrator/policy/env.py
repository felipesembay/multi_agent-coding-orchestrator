"""Exact subprocess allowlists. Values stay in memory, never in policy snapshots."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
import re

INTERNAL_SCOPES = frozenset({'runner', 'tests', 'git'})
BASE_VARIABLES = frozenset({
    'PATH', 'HOME', 'USER', 'LOGNAME', 'LANG', 'LANGUAGE', 'TERM', 'COLORTERM',
    'SHELL', 'TMPDIR', 'TMP', 'TEMP', 'VIRTUAL_ENV',
    'LC_ALL', 'LC_CTYPE', 'LC_MESSAGES', 'LC_COLLATE', 'LC_MONETARY', 'LC_NUMERIC',
    'LC_TIME', 'LC_PAPER', 'LC_NAME', 'LC_ADDRESS', 'LC_TELEPHONE', 'LC_MEASUREMENT',
    'LC_IDENTIFICATION', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME',
    'XDG_STATE_HOME', 'XDG_RUNTIME_DIR', 'XDG_CONFIG_DIRS', 'XDG_DATA_DIRS',
    'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'NODE_EXTRA_CA_CERTS',
})
BUILTIN_CONFIG_VARIABLES = frozenset({'CLAUDE_CONFIG_DIR', 'CODEX_HOME'})
RUNNER_VARIABLES = frozenset({'ORCH_DB', 'ORCH_ALLOWED_ROOTS', 'ORCH_ALLOWED_TEST_COMMANDS'})
_active_config = ContextVar('subprocess_environment_config', default=None)
_active_scope = ContextVar('subprocess_environment_scope', default=('tests', frozenset()))


class EnvironmentPolicyError(ValueError):
    pass


def validate_env_names(names):
    if isinstance(names, str) or not isinstance(names, (list, tuple, set, frozenset)):
        raise EnvironmentPolicyError('Invalid subprocess environment allowlist')
    for name in names:
        if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name)
                or name.startswith(('ORCH_', 'GIT_', 'LD_', 'DYLD_'))
                or name in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'PYTHONINSPECT')
                or re.search(r'(^|_)(KEY|TOKEN|SECRET|PASSWORD|CREDENTIALS?)(_|$)', name, re.I)):
            raise EnvironmentPolicyError('Unsupported subprocess environment variable declaration')
    return frozenset(names)


def parse_allowlist(raw):
    try:
        config = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        raise EnvironmentPolicyError('Invalid subprocess environment allowlist') from None
    if not isinstance(config, dict):
        raise EnvironmentPolicyError('Invalid subprocess environment allowlist')
    result = {}
    for scope, names in config.items():
        if not isinstance(scope, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', scope) or not isinstance(names, list):
            raise EnvironmentPolicyError('Invalid subprocess environment allowlist')
        selected = validate_env_names(names)
        if selected:
            result[scope] = sorted(selected)
    return dict(sorted(result.items()))


def snapshot_allowlist(config):
    raw = config.get('environment_allowlist')
    if raw is not None and not isinstance(raw, dict):
        raise EnvironmentPolicyError('Invalid saved subprocess environment allowlist')
    return parse_allowlist({} if raw is None else raw)


def current_allowlist():
    configured = _active_config.get()
    return parse_allowlist(os.environ.get('ORCH_ENV_ALLOWLIST', '{}') if configured is None else configured)


@contextmanager
def environment_config(config):
    token = _active_config.set(parse_allowlist(config))
    try:
        yield
    finally:
        _active_config.reset(token)


@contextmanager
def environment_scope(scope, declared=()):
    if scope in INTERNAL_SCOPES:
        raise EnvironmentPolicyError('Internal subprocess scopes cannot identify adapters')
    token = _active_scope.set((scope, validate_env_names(declared)))
    try:
        yield
    finally:
        _active_scope.reset(token)


def safe_env(scope, *, source=None, declared=()):
    """Explicit source replaces inheritance; generated supervision/Git controls win."""
    source = os.environ if source is None else source
    config = current_allowlist()
    allowed = BASE_VARIABLES | validate_env_names(declared) | set(config.get(scope, ()))
    if scope == 'runner':
        allowed |= RUNNER_VARIABLES | BUILTIN_CONFIG_VARIABLES
        # Runner needs the explicitly authorized inputs of its downstream scopes.
        allowed |= {name for names in config.values() for name in names}
    result = {key: value for key, value in source.items() if key in allowed}
    result.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    if os.environ.get('ORCH_DISPATCH_TOKEN'):
        result['ORCH_DISPATCH_TOKEN'] = os.environ['ORCH_DISPATCH_TOKEN']
    if scope == 'runner':
        result['ORCH_ENV_ALLOWLIST'] = json.dumps(config, sort_keys=True)
    return result


def command_env(argv, source=None):
    scope, declared = _active_scope.get()
    if os.path.basename(argv[0]) == 'git':
        scope, declared = 'git', ()
    return safe_env(scope, source=source, declared=declared)
