"""Build bounded review text on the host; API providers never receive a path.

Fail closed on missing evidence, binary/unreadable files or symlink traversal.
Directory descriptors plus O_NOFOLLOW also reject paths swapped while reading.
"""
import os

from .base import ContextItem


def review_context(worktree, *, runner, timeout):
    diff = runner(['git', 'diff', '--no-ext-diff', 'HEAD'], worktree, timeout())
    statistics = runner(['git', 'diff', '--numstat', 'HEAD'], worktree, timeout())
    for line in statistics.splitlines():
        counts = line.split('\t', 2)
        if len(counts) != 3 or any(not count.isdecimal() for count in counts[:2]):
            raise ValueError('Binary or unsupported tracked review evidence')
    status = runner(['git', 'status', '--porcelain=v1', '-z', '--untracked-files=all'], worktree, timeout())
    if len(diff) > 32000 or len(status) > 16000:
        raise ValueError('Review evidence exceeds supported context limits')
    items = [ContextItem(label='Tracked changes', text=diff), ContextItem(label='Git status', text=status)]
    # Renames have an extra NUL-delimited path: skip it, do not interpret as a status.
    entries = iter(status.split('\0'))
    paths = []
    for entry in entries:
        if not entry: continue
        if entry[:2] == '??': paths.append(entry[3:])
        elif 'R' in entry[:2] or 'C' in entry[:2]: next(entries, None)
    if len(paths) > 14: raise ValueError('Too many untracked files for model review')
    total = len(diff) + len(status)
    for relative in paths:
        parts = relative.split('/')
        if not parts or any(part in ('', '.', '..') for part in parts):
            raise ValueError('Invalid review evidence path')
        descriptor = os.open(worktree, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                os.close(descriptor); descriptor = child
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
            with os.fdopen(fd, 'rb') as stream:
                import stat
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('Non-regular or shared review evidence')
                data = stream.read(32001)
            if len(data) > 32000 or b'\0' in data: raise ValueError('Unsupported review evidence')
            text = data.decode('utf-8')
            total += len(text)
            if total > 64000: raise ValueError('Review evidence exceeds supported context limits')
            items.append(ContextItem(label=relative[:100], text=text))
        finally:
            os.close(descriptor)
    return items
