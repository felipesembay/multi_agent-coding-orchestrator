"""Deterministic worktree state digest for side-effect tracking (V2-RES-001 / PERSISTENCE.md §6.2).

tree_digest = SHA-256 of:
- `git status --porcelain=v2`
- `git diff --no-ext-diff HEAD`
- bounded content hashes of untracked files (up to 64 files, 64 KiB per file)
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Optional

from .. import core

_MAX_UNTRACKED_FILES = 64
_MAX_UNTRACKED_BYTES_PER_FILE = 65536


def current_git_head(
    worktree: str | Path,
    *,
    runner: Callable[..., str] = core.run_command,
    timeout: int = 60,
) -> Optional[str]:
    wt = Path(worktree)
    if not wt.is_dir() or not (wt / ".git").exists():
        return None
    try:
        out = runner(["git", "rev-parse", "HEAD"], str(wt), timeout).strip()
        return out or None
    except Exception:
        return None


def _untracked_paths_from_porcelain_v2(porcelain_output: str) -> list[str]:
    paths: list[str] = []
    for line in porcelain_output.splitlines():
        if line.startswith("? "):
            rel = line[2:].strip()
            if rel:
                paths.append(rel)
        elif line.startswith("?? "):
            rel = line[3:].strip()
            if rel:
                paths.append(rel)
    return sorted(set(paths))


def compute_tree_digest(
    worktree: str | Path,
    *,
    runner: Callable[..., str] = core.run_command,
    timeout: int = 60,
) -> Optional[str]:
    wt = Path(worktree)
    if not wt.is_dir() or not (wt / ".git").exists():
        return None
    try:
        status_out = runner(["git", "status", "--porcelain=v2"], str(wt), timeout)
        diff_out = runner(["git", "diff", "--no-ext-diff", "HEAD"], str(wt), timeout)
    except Exception:
        return None

    digest = hashlib.sha256()
    digest.update(b"status\0")
    digest.update(status_out.encode("utf-8", errors="replace"))
    digest.update(b"\0diff\0")
    digest.update(diff_out.encode("utf-8", errors="replace"))
    digest.update(b"\0untracked\0")

    root = wt.resolve()
    untracked = _untracked_paths_from_porcelain_v2(status_out)
    for rel_path in untracked[:_MAX_UNTRACKED_FILES]:
        candidate = (root / rel_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        digest.update(rel_path.encode("utf-8", errors="replace"))
        digest.update(b"\0")
        if candidate.is_file() and not candidate.is_symlink():
            try:
                with candidate.open("rb") as fh:
                    chunk = fh.read(_MAX_UNTRACKED_BYTES_PER_FILE)
                file_hash = hashlib.sha256(chunk).hexdigest()
                digest.update(file_hash.encode("ascii"))
            except OSError:
                digest.update(b"unreadable")
        digest.update(b"\0")

    return digest.hexdigest()
