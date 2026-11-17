"""Runtime contracts and measured invocations without CLI telemetry assumptions.

Manifests, probing and plugin registration belong to CORE-003. CLIs keep usage
unavailable until parsers have been verified; no raw CLI content is retained.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Literal, Optional, Protocol
import uuid

from pydantic import BaseModel, Field, model_validator

from .errors import ErrorCode, error_code


class InvocationRequest(BaseModel):
    role: str = 'legacy'
    prompt: str
    cwd: str
    model: Optional[str] = None
    permission: Literal['read_only', 'workspace_write']
    output_schema: Optional[dict] = None
    timeout_s: int = 600
    # None retains the legacy inherited environment until SEC-002.
    env: Optional[dict[str, str]] = None


class UsageReport(BaseModel):
    input_tokens: Optional[int] = Field(default=None, ge=0)
    output_tokens: Optional[int] = Field(default=None, ge=0)
    cache_read_tokens: Optional[int] = Field(default=None, ge=0)
    cache_write_tokens: Optional[int] = Field(default=None, ge=0)
    reasoning_tokens: Optional[int] = Field(default=None, ge=0)
    reported_cost_usd: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    source: Literal['provider_reported', 'cli_reported', 'estimated', 'unavailable'] = 'unavailable'
    raw: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def unavailable_has_no_values(self):
        if self.source == 'unavailable' and any(
            getattr(self, name) is not None for name in (
                'input_tokens', 'output_tokens', 'cache_read_tokens',
                'cache_write_tokens', 'reasoning_tokens', 'reported_cost_usd',
            )
        ):
            raise ValueError('Unavailable usage cannot claim token counts or cost')
        return self


class InvocationResult(BaseModel):
    text: str
    structured: Optional[dict] = None
    usage: UsageReport = Field(default_factory=UsageReport)
    duration_ms: int = Field(default=0, ge=0)
    model_reported: Optional[str] = None
    session_id: Optional[str] = None
    error_code: Optional[ErrorCode] = None


class AgentCall(BaseModel):
    """Metadata only: never includes prompts, output, cwd, env or error messages."""
    call_id: str
    provider: str
    role: str
    model: Optional[str] = None  # Requested model; None means CLI default unknown.
    model_reported: Optional[str] = None
    session_id: Optional[str] = None
    duration_ms: int = Field(ge=0)
    usage: UsageReport = Field(default_factory=UsageReport)
    billing_mode: Literal['api_metered', 'subscription_quota', 'local', 'unknown'] = 'unknown'
    error_code: Optional[ErrorCode] = None


class AgentRuntime(Protocol):
    def invoke(self, req: InvocationRequest) -> InvocationResult: ...


class CommandRunner(Protocol):
    def __call__(self, argv: list[str], cwd: str, timeout: int,
                 env: Optional[dict] = None) -> str: ...


class CommandRuntime:
    """Inject execution and an optional metadata sink; no dependency on core/DB."""

    provider: str

    def __init__(self, runner: CommandRunner,
                 observer: Optional[Callable[[AgentCall], None]] = None):
        self._runner = runner
        self._observer = observer

    def _resolve_model(self, req: InvocationRequest) -> Optional[str]:
        return req.model

    def invoke(self, req: InvocationRequest) -> InvocationResult:
        req = req.model_copy(update={'model': self._resolve_model(req)})
        call_id = str(uuid.uuid4())
        started = time.monotonic_ns()
        try:
            result = self._invoke(req)
        except Exception as exc:
            duration = max(0, (time.monotonic_ns() - started) // 1000000)
            if self._observer is not None:
                try:
                    self._observer(AgentCall(
                        call_id=call_id, provider=self.provider, role=req.role,
                        model=req.model, duration_ms=duration, error_code=error_code(exc),
                    ))
                except Exception:
                    # Metadata persistence must not replace the primary CLI error.
                    logging.getLogger(__name__).warning('Could not record failed agent call metadata')
            raise
        result.duration_ms = max(0, (time.monotonic_ns() - started) // 1000000)
        if self._observer is not None:
            self._observer(AgentCall(
                call_id=call_id, provider=self.provider, role=req.role, model=req.model,
                model_reported=result.model_reported, session_id=result.session_id,
                duration_ms=result.duration_ms, usage=result.usage, error_code=result.error_code,
            ))
        return result

    def _invoke(self, req: InvocationRequest) -> InvocationResult:
        raise NotImplementedError

    def _run(self, argv: list[str], req: InvocationRequest) -> str:
        if req.env is None:
            return self._runner(argv, req.cwd, req.timeout_s)
        return self._runner(argv, req.cwd, req.timeout_s, env=req.env)
