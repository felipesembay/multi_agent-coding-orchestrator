"""Conservative error classification for metadata; never changes legacy errors."""
import subprocess
from typing import Literal, get_args

ErrorCode = Literal[
    'rate_limited', 'quota_exhausted', 'auth_failed', 'timeout',
    'invalid_output', 'permission_denied', 'unavailable', 'unknown',
]


class InvocationFailure(RuntimeError):
    """Trusted adapter error; safe_to_retry attests no effects were performed.

    Text classification is metadata only. Adapters must opt in after verifying
    a rejection before tool execution, never infer safety from stderr wording.
    """
    def __init__(self, code: ErrorCode, *, safe_to_retry: bool = False):
        if code not in get_args(ErrorCode) or type(safe_to_retry) is not bool:
            raise ValueError('Invalid normalized invocation failure')
        super().__init__('Agent invocation failed: ' + code)
        self.code = code
        self.safe_to_retry = safe_to_retry


def error_code(exc: Exception) -> ErrorCode:
    if isinstance(exc, InvocationFailure):
        return exc.code
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
