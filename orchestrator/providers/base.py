"""Runtime contracts and measured invocations without CLI telemetry assumptions.

Manifest discovery and passive probes never invoke agents. CLIs keep usage
unavailable until parsers have been verified; no raw CLI content is retained.
"""
from __future__ import annotations

from enum import Enum
import logging
import shutil
import time
from typing import Callable, Literal, Optional, Protocol
import uuid
from datetime import datetime,timezone

from pydantic import BaseModel, Field, ValidationError, field_serializer, field_validator, model_validator

from .errors import ErrorCode, error_code
from ..policy.env import INTERNAL_SCOPES, environment_scope, safe_env, validate_env_names


class Capability(str, Enum):
    TEXT = 'text'
    STRUCTURED_OUTPUT = 'structured_output'
    PLANNING = 'planning'
    CODE_EDIT = 'code_edit'
    CODE_EXEC = 'code_exec'
    TOOL_CALLING = 'tool_calling'
    REVIEW = 'review'
    STREAMING = 'streaming'
    REPO_CONTEXT = 'repo_context'
    USAGE_METRICS = 'usage_metrics'
    COST_REPORT = 'cost_report'
    SESSION_RESUME = 'session_resume'


class CapabilityManifest(BaseModel):
    model_config = {'extra': 'forbid'}
    adapter: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,63}$')
    kind: Literal['agent_runtime', 'model_provider']
    capabilities: set[Capability]
    permission_modes: list[Literal['read_only', 'workspace_write']]
    auth_modes: list[Literal['cli_managed', 'api_key', 'oauth', 'none']]
    billing_mode: Literal['api_metered', 'subscription_quota', 'local', 'unknown']
    usage_source: Literal['provider_reported', 'cli_reported', 'none']
    verified: bool
    environment_variables: set[str] = Field(default_factory=set)

    @field_validator('adapter')
    @classmethod
    def reserved_internal_scope(cls, value):
        if value in INTERNAL_SCOPES:
            raise ValueError('Internal subprocess scopes cannot identify adapters')
        return value

    @field_validator('environment_variables')
    @classmethod
    def safe_variable_declarations(cls, value):
        return set(validate_env_names(value))

    @field_serializer('environment_variables')
    def sorted_environment_variables(self, value):
        return sorted(value)

    @field_serializer('capabilities')
    def sorted_capabilities(self, value):
        return sorted(capability.value for capability in value)


class ProbeResult(BaseModel):
    """Executable discovery only; presence does not imply authentication or quota."""
    model_config = {'extra': 'forbid'}
    executable_found: Optional[bool] = None
    version: Optional[str] = Field(default=None, max_length=80,
                                  pattern=r'^[0-9]+(?:\.[0-9]+){1,3}(?:[-+][a-zA-Z0-9.-]+)?$')
    credential_present: Optional[bool] = None
    error_code: Optional[Literal[
        'probe_failed', 'load_failed', 'invalid_provider', 'duplicate_entry_point',
        'entry_point_missing',
    ]] = None


class InvocationRequest(BaseModel):
    role: str = 'legacy'
    prompt: str
    cwd: str
    model: Optional[str] = None
    permission: Literal['read_only', 'workspace_write']
    output_schema: Optional[dict] = None
    timeout_s: int = 600
    # None selects ambient allowlisted values; explicit env is a filtered replacement.
    env: Optional[dict[str, str]] = None


class GenerationRequest(BaseModel):
    """Text-only API request: no filesystem path, environment or tool executor."""
    model_config = {'extra': 'forbid', 'revalidate_instances': 'always'}
    role: Literal['planner', 'reviewer', 'documenter']
    prompt: str = Field(max_length=100000, repr=False)
    model: str = Field(min_length=3, max_length=256, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._:-]*/[a-zA-Z0-9][a-zA-Z0-9._:/-]*$')
    permission: Literal['read_only'] = 'read_only'
    credential_ref: str = Field(min_length=1, max_length=256, repr=False, exclude=True)
    timeout_s: int = Field(default=600, strict=True, ge=1, le=86400)


class ContextItem(BaseModel):
    model_config = {'extra': 'forbid'}
    label: str = Field(max_length=100)
    text: str = Field(max_length=32000, repr=False)


class ModelInfo(BaseModel):
    model_config = {'extra': 'forbid'}
    id: str = Field(min_length=1, max_length=256)
    name: str = Field(max_length=256)
    context_length: Optional[int] = Field(default=None, strict=True, ge=1)


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
    started_at: Optional[str] = Field(default=None,max_length=64)

    @field_validator('started_at')
    @classmethod
    def aware_start(cls,value):
        if value is None:return value
        try:
            parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
            if parsed.utcoffset() is None:raise ValueError()
            return parsed.astimezone(timezone.utc).isoformat()
        except Exception:
            raise ValueError('Invocation timestamp must include timezone') from None


def invoke_measured(provider: str, req: InvocationRequest,
                    invoke: Callable[[], InvocationResult],
                    observer: Optional[Callable[[AgentCall], None]] = None, *,
                    call_id: Optional[str] = None) -> InvocationResult:
    """Measure a call at a single owned boundary, including registered plugins."""
    call_id = call_id or str(uuid.uuid4())
    started_stamp = datetime.now(timezone.utc).isoformat()
    started = time.monotonic_ns()
    try:
        raw = invoke()
        try:
            result = InvocationResult.model_validate(raw)
        except ValidationError:
            raise RuntimeError('Agent runtime returned invalid InvocationResult') from None
    except Exception as exc:
        duration = max(0, (time.monotonic_ns() - started) // 1000000)
        if observer is not None:
            try:
                observer(AgentCall(
                    call_id=call_id, provider=provider, role=req.role,
                    model=req.model, duration_ms=duration, error_code=error_code(exc),started_at=started_stamp,
                ))
            except Exception:
                # Metadata persistence must not replace the primary CLI error.
                logging.getLogger(__name__).warning('Could not record failed agent call metadata')
        raise
    result.duration_ms = max(0, (time.monotonic_ns() - started) // 1000000)
    if observer is not None:
        observer(AgentCall(
            call_id=call_id, provider=provider, role=req.role, model=req.model,
            model_reported=result.model_reported, session_id=result.session_id,
            duration_ms=result.duration_ms, usage=result.usage, error_code=result.error_code,started_at=started_stamp,
        ))
    return result


class AgentRuntime(Protocol):
    manifest: CapabilityManifest

    def probe(self) -> ProbeResult: ...

    def invoke(self, req: InvocationRequest) -> InvocationResult: ...


class ModelProvider(Protocol):
    manifest: CapabilityManifest

    def probe(self) -> ProbeResult: ...
    def list_models(self) -> list[ModelInfo]: ...
    def generate(self, req: GenerationRequest, context: list[ContextItem]) -> InvocationResult: ...


class CommandRunner(Protocol):
    def __call__(self, argv: list[str], cwd: str, timeout: int,
                 env: Optional[dict] = None) -> str: ...


class CommandRuntime:
    """Inject execution and an optional metadata sink; no dependency on core/DB."""

    provider: str
    executable: str
    manifest: CapabilityManifest

    def probe(self) -> ProbeResult:
        return ProbeResult(executable_found=shutil.which(self.executable) is not None)

    def __init__(self, runner: CommandRunner,
                 observer: Optional[Callable[[AgentCall], None]] = None):
        self._runner = runner
        self._observer = observer
        self.manifest = type(self).manifest.model_copy(deep=True)
        if self.provider != self.manifest.adapter:
            raise ValueError('Runtime provider must match manifest adapter')

    def _resolve_model(self, req: InvocationRequest) -> Optional[str]:
        return req.model

    def invoke(self, req: InvocationRequest) -> InvocationResult:
        req = req.model_copy(update={'model': self._resolve_model(req)})
        return invoke_measured(self.provider, req, lambda: self._invoke(req), self._observer)

    def _invoke(self, req: InvocationRequest) -> InvocationResult:
        raise NotImplementedError

    def _run(self, argv: list[str], req: InvocationRequest) -> str:
        if self.provider != self.manifest.adapter:
            raise ValueError('Runtime provider must match manifest adapter')
        with environment_scope(self.manifest.adapter, self.manifest.environment_variables):
            env = safe_env(self.manifest.adapter, source=req.env, declared=self.manifest.environment_variables)
            return self._runner(argv, req.cwd, req.timeout_s, env=env)
