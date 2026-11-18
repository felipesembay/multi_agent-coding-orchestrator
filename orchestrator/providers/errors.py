"""Conservative error classification for metadata; never changes legacy errors."""
import subprocess
from typing import Literal

ErrorCode = Literal[
    'rate_limited', 'quota_exhausted', 'auth_failed', 'timeout',
    'invalid_output', 'permission_denied', 'unavailable', 'unknown',
]


def error_code(exc: Exception) -> ErrorCode:
    if isinstance(exc, (TimeoutError, subprocess.TimeoutExpired)):
        return 'timeout'
    if isinstance(exc, PermissionError):
        return 'permission_denied'
    if isinstance(exc, FileNotFoundError):
        return 'unavailable'
    message = str(exc).lower()
    for code, markers in (
        ('rate_limited', ('rate limit', 'rate_limit')),
        ('quota_exhausted', ('usage limit', 'usage_limit', 'quota exceeded',
                             'out of extra usage', 'hit your limit', 'you have reached your limit')),
        ('auth_failed', ('authentication failed', 'unauthorized', 'invalid api key', 'auth failed')),
        ('timeout', ('timed out',)),
        ('invalid_output', ('invalid cli json', 'empty or invalid response', 'invalid invocationresult')),
        ('permission_denied', ('permission denied', 'denied requiredactions')),
        ('unavailable', ('executable missing:',)),
    ):
        if any(marker in message for marker in markers):
            return code
    return 'unknown'
