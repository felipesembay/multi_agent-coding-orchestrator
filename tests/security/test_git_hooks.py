"""Real Git sentinels: controls prove executability, hardened paths never run them."""
import os
from pathlib import Path
import shlex
import subprocess

import pytest

from orchestrator import core, projects, repository_lock
from orchestrator.policy.env import safe_env


def git(repo, *args, check=True):
    return subprocess.run(['git', '--no-pager', '-c', 'user.name=Fixture',
        '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false', *args],
        cwd=repo, env=safe_env('git'), capture_output=True, text=True, check=check, timeout=5)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.delenv('ORCH_ENV_ALLOWLIST', raising=False)
    monkeypatch.setenv('ORCH_WORKTREES', str(tmp_path / 'trees'))
    path = tmp_path / 'repo'
    path.mkdir()
    git(path, 'init', '--template=')
    (path / 'payload.txt').write_text('before\n')
    (path / '.gitattributes').write_text('payload.txt diff=sentinel filter=sentinel\n')
    git(path, 'add', '.')
    git(path, 'commit', '-m', 'fixture')
    return path


def sentinel(tmp_path, name, tail=''):
    marker = tmp_path / (name + '-executed')
    script = tmp_path / name
    script.write_text('#!/bin/sh\nprintf executed > ' + shlex.quote(str(marker)) + '\n' + tail)
    script.chmod(0o755)
    return script, marker


def test_post_checkout_hook_control_and_prepare_are_safe(repo, tmp_path):
    hook, marker = sentinel(tmp_path, 'post-checkout')
    git(repo, 'config', 'core.hooksPath', str(tmp_path))
    git(repo, 'worktree', 'add', '-b', 'control', str(tmp_path / 'control-tree'), 'HEAD')
    assert marker.read_text() == 'executed'  # Positive control on this installed Git.
    marker.unlink()
    before_config = (repo / '.git/config').read_bytes()
    head = git(repo, 'rev-parse', 'HEAD').stdout.strip()
    with repository_lock.repository_lock(repo):
        tree = core.prepare(repo, 'run-' + 'a' * 12)
    assert not marker.exists()
    assert (tree / 'payload.txt').read_text() == 'before\n'
    assert git(tree, 'status', '--porcelain').stdout == ''
    assert git(tree, 'rev-parse', 'HEAD').stdout.strip() == head
    assert git(tree, 'branch', '--show-current').stdout.strip() == 'agent/run-' + 'a' * 12
    assert (repo / '.git/config').read_bytes() == before_config


def test_fsmonitor_control_and_all_git_helpers_are_safe(repo, tmp_path):
    script, marker = sentinel(tmp_path, 'fsmonitor', "printf 'token\\0'\n")
    git(repo, 'config', 'core.fsmonitor', str(script))
    (repo / 'payload.txt').write_text('after\n')
    git(repo, 'status', '--porcelain')
    assert marker.exists()
    marker.unlink()
    assert core.run_command(['git', 'status', '--porcelain'], str(repo))
    assert not marker.exists()
    assert projects.git(repo, 'status', '--porcelain')
    assert not marker.exists()
    assert repository_lock.identity(repo) == str(repo / '.git')
    assert not marker.exists()


@pytest.mark.parametrize('conversion,flag', [('command', '--ext-diff'), ('textconv', '--no-ext-diff')])
def test_diff_helpers_are_executable_in_control_but_disabled_in_core(repo, tmp_path, conversion, flag):
    script, marker = sentinel(tmp_path, 'diff-helper', 'cat "$1"\n' if conversion == 'textconv' else '')
    git(repo, 'config', 'diff.sentinel.' + conversion, str(script))
    (repo / 'payload.txt').write_text('after\n')
    git(repo, 'diff', flag, 'HEAD')
    assert marker.exists()
    marker.unlink()
    output = core.run_command(['git', 'diff', 'HEAD'], str(repo))
    assert '+after' in output
    assert not marker.exists()


@pytest.mark.parametrize('kind', ['clean', 'smudge', 'process'])
def test_configured_execution_filters_fail_closed_before_running(repo, tmp_path, kind):
    script, marker = sentinel(tmp_path, 'content-filter', 'cat\n')
    git(repo, 'config', 'filter.sentinel.' + kind, str(script))
    if kind == 'smudge':
        git(repo, 'worktree', 'add', '-b', 'control-filter', str(tmp_path / 'control-filter'), 'HEAD', check=False)
    else:
        (repo / 'payload.txt').write_text('after\n')
        git(repo, 'hash-object', '--path=payload.txt', 'payload.txt', check=False)
    assert marker.exists()
    marker.unlink()
    with pytest.raises(ValueError, match='filter'):
        core.prepare(repo, 'run-' + 'b' * 12)
    assert not marker.exists()
    assert not (tmp_path / 'trees' / ('run-' + 'b' * 12)).exists()


def test_branch_conditional_filter_is_checked_before_checkout(repo, tmp_path):
    script, marker = sentinel(tmp_path, 'branch-filter', 'cat\n')
    included = tmp_path / 'branch.config'
    included.write_text('[filter "sentinel"]\n\tsmudge = ' + str(script) + '\n')
    git(repo, 'config', 'includeIf.onbranch:agent/**.path', str(included))
    assert git(repo, 'config', '--get', 'filter.sentinel.smudge', check=False).returncode == 1
    with pytest.raises(ValueError, match='filter'):
        core.prepare(repo, 'run-' + 'c' * 12)
    assert not marker.exists()
    # Newly registered empty worktree is retained for inspection; no files checked out.
    tree = tmp_path / 'trees' / ('run-' + 'c' * 12)
    assert git(tree, 'config', '--get', 'filter.sentinel.smudge').stdout.strip() == str(script)
    assert not (tree / 'payload.txt').exists()


def test_git_alias_cannot_execute_shell_through_run_command(repo, tmp_path):
    script, marker = sentinel(tmp_path, 'alias-helper')
    git(repo, 'config', 'alias.unsafe-sentinel', '!' + str(script))
    git(repo, 'unsafe-sentinel')
    assert marker.exists()
    marker.unlink()
    with pytest.raises(ValueError, match='Git invocation'):
        core.run_command(['git', 'unsafe-sentinel'], str(repo))
    assert not marker.exists()


@pytest.mark.parametrize('arguments', [
    ['-c', 'core.hooksPath=/tmp/unsafe', 'status'],
    ['--exec-path=/tmp/unsafe', 'status'], ['diff', '--textconv', 'HEAD'],
    ['diff', '--ext-diff', 'HEAD'], ['status', '--ignore-submodules=none'],
    ['worktree', 'add', '/tmp/unreachable-target'], ['add', '--edit'],
    ['reset', '--patch'], ['commit', '--edit'], ['status', '--no-ignore-submodules'],
    ['diff', '--textco', 'HEAD'], ['diff', '--ext-dif', 'HEAD'],
])
def test_unsafe_global_options_and_explicit_diff_helpers_are_rejected(repo, arguments):
    with pytest.raises(ValueError, match='Git invocation'):
        core.run_command(['git', *arguments], str(repo))


def test_abbreviated_checkout_cannot_bypass_conditional_filter_check(repo, tmp_path):
    script, marker = sentinel(tmp_path, 'abbreviation-filter', 'cat\n')
    included = tmp_path / 'abbreviation.config'
    included.write_text('[filter "sentinel"]\n\tsmudge = ' + str(script) + '\n')
    git(repo, 'config', 'includeIf.onbranch:agent/**.path', str(included))
    target = tmp_path / 'abbreviated-target'
    arguments = ['worktree', 'add', '--no-checkout', '--check', '-b',
                 'agent/run-' + 'd' * 12, str(target), 'HEAD']
    with pytest.raises(ValueError, match='Git invocation'):
        core.run_command(['git', *arguments], str(repo))
    assert not marker.exists() and not target.exists()
