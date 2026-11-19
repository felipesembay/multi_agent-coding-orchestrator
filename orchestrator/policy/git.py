"""Fixed Git policy for orchestration commands, never a general Git shell wrapper."""
import os
import re
import subprocess
import time

SAFE_CONFIG = (
    ('core.hooksPath', os.devnull), ('core.fsmonitor', 'false'),
    ('commit.gpgsign', 'false'), ('tag.gpgsign', 'false'),
    ('submodule.recurse', 'false'), ('status.submoduleSummary', 'false'),
    ('gc.auto', '0'), ('maintenance.auto', 'false'), ('checkout.workers', '1'),
)
COMMANDS = frozenset({'init', 'add', 'commit', 'status', 'rev-parse', 'worktree', 'reset', 'diff'})


class UnsafeGitConfiguration(ValueError):
    pass


def _prefix(executable, config):
    result = [executable, '--no-pager']
    # Trusted caller defaults first; non-overridable security settings last.
    for key, value in (*config, *SAFE_CONFIG):
        result.extend(['-c', key + '=' + value])
    return result


def _command(argv, config):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        raise UnsafeGitConfiguration('Unsupported or unsafe Git invocation')
    command, args = argv[1], list(argv[2:])
    options = args[:args.index('--')] if '--' in args else args
    # Match complete forms rather than interpreting Git's option abbreviations.
    if command == 'init':
        valid = args == ['--template=']
    elif command == 'add':
        valid = len(args) >= 2 and args[0] == '--'
    elif command == 'commit':
        valid = len(args) == 2 and args[0] == '-m'
    elif command == 'reset':
        valid = args == ['--hard', 'HEAD']
    elif command == 'worktree':
        valid = (len(args) == 6 and args[:3] == ['add', '--no-checkout', '-b']
                 and re.fullmatch(r'agent/run-[0-9a-f]{12}', args[3])
                 and os.path.isabs(args[4]) and args[5] == 'HEAD')
    elif command == 'status':
        valid = options in ([], ['--porcelain'], ['--porcelain=v2'], ['--short'])
    elif command == 'rev-parse':
        valid = args in (['--git-common-dir'], ['--show-toplevel'], ['--verify', 'HEAD'], ['HEAD'])
    else:  # diff: only non-executing options and the current HEAD.
        valid = (all(arg in ('HEAD', '--no-ext-diff', '--no-textconv', '--ignore-submodules=all') for arg in options)
                 and options.count('HEAD') <= 1)
    if not valid:
        raise UnsafeGitConfiguration('Unsupported or unsafe Git invocation')
    if command == 'diff':
        args = ['--no-ext-diff', '--no-textconv', '--ignore-submodules=all', *args]
    elif command == 'status':
        args = ['--ignore-submodules=all', *args]
    return [*_prefix(argv[0], config), command, *args]


def run_git(argv, *, cwd, env, timeout, pass_fds=(), config=()):
    """Reject executable content filters before touching index/worktree data.

    Each query uses the effective config of this cwd/branch, including includes.
    Total query+command time is charged to the existing caller timeout. Config
    command values and query stderr are never included in exceptions.
    """
    command = _command(argv, config)
    deadline = time.monotonic() + timeout

    def run(arguments):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(argv, timeout)
        return subprocess.run(arguments, cwd=cwd, env=env, timeout=remaining,
                              pass_fds=pass_fds, text=True, capture_output=True, check=False)

    if argv[1] != 'init':
        query = run([*_prefix(argv[0], config), 'config', '--includes', '--null',
                     '--get-regexp', r'^filter\..*\.(clean|smudge|process)$'])
        if query.returncode not in (0, 1):
            raise UnsafeGitConfiguration('Unable to validate Git filter configuration')
        for item in query.stdout.split('\0'):
            if not item:
                continue
            _key, separator, value = item.partition('\n')
            if not separator or not re.fullmatch(r'filter\..*\.(clean|smudge|process)', _key) or value.strip():
                raise UnsafeGitConfiguration('Executable Git content filters are unsupported; inspect repository configuration')
    return run(command)
