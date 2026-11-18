"""Typed role bindings; environment is only an input to the legacy preset."""
import os
from typing import Literal, Mapping, Optional

from pydantic import BaseModel, Field, model_validator

from .base import Capability

DEFAULT_AGY_MODEL = 'gemini-4-argon-medium'
ALIASES = {'claude': 'claude_code', 'codex': 'codex_cli', 'antigravity': 'antigravity'}
LEGACY_NAMES = {value: key for key, value in ALIASES.items()}


class RoleBinding(BaseModel):
    model_config = {'extra': 'forbid', 'frozen': True}
    adapter: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,63}$')
    model: Optional[str] = None
    permission: Literal['read_only', 'workspace_write']

    @model_validator(mode='before')
    @classmethod
    def resolve_antigravity_default(cls, value):
        if isinstance(value, dict) and value.get('adapter') == 'antigravity' and value.get('model') is None:
            return {**value, 'model': DEFAULT_AGY_MODEL}
        return value


class AgentBindings(BaseModel):
    """Configuration of the current linear graph, not a new workflow preset."""
    model_config = {'extra': 'forbid', 'frozen': True}
    schema_version: Literal[1] = 1
    preset: Literal['legacy-v1'] = 'legacy-v1'
    planner: RoleBinding
    implementer: RoleBinding
    reviewer: RoleBinding
    planner_fallback: Optional[RoleBinding] = None
    agent_timeout: int = Field(default=900, ge=1, le=86400)


def legacy_agent_settings(environ: Optional[Mapping[str, str]] = None):
    """Preserve the old flat snapshot/digest, even for invalid preflight inputs."""
    env = os.environ if environ is None else environ
    planner = env.get('ORCH_PLANNER', 'claude').lower()
    implementer = env.get('ORCH_IMPLEMENTER', 'claude').lower()
    return dict(
        planner=planner, implementer=implementer, reviewer='codex',
        planner_model=env.get('ORCH_PLANNER_MODEL', DEFAULT_AGY_MODEL) if planner == 'antigravity' else None,
        implementer_model=env.get('ORCH_IMPLEMENTER_MODEL', DEFAULT_AGY_MODEL) if implementer == 'antigravity' else None,
        planner_fallback_model=env.get('ORCH_PLANNER_MODEL', DEFAULT_AGY_MODEL),
        agent_timeout=int(env.get('AGENT_TIMEOUT', '900')),
    )


def _legacy_binding(provider, role, model=None):
    adapter = ALIASES.get(provider, provider)
    permission = 'workspace_write' if role == 'implementer' or (role == 'planner' and adapter == 'claude_code') else 'read_only'
    return RoleBinding(adapter=adapter, model=model if adapter == 'antigravity' else None, permission=permission)


def legacy_bindings(environ: Optional[Mapping[str, str]] = None) -> AgentBindings:
    return _bindings_from_flat(legacy_agent_settings(environ), managed_snapshot=False)


def legacy_projection(config: AgentBindings):
    """Flat fields retained for existing API/UI consumers alongside new bindings."""
    return dict(
        planner=LEGACY_NAMES.get(config.planner.adapter, config.planner.adapter),
        implementer=LEGACY_NAMES.get(config.implementer.adapter, config.implementer.adapter),
        reviewer=LEGACY_NAMES.get(config.reviewer.adapter, config.reviewer.adapter),
        planner_model=config.planner.model, implementer_model=config.implementer.model,
        planner_fallback_model=config.planner_fallback.model if config.planner_fallback else DEFAULT_AGY_MODEL,
        agent_timeout=config.agent_timeout,
    )


def bindings_from_snapshot(config) -> AgentBindings:
    """Never read the current environment while decoding a saved snapshot."""
    if config.get('bindings') is not None:
        result = AgentBindings.model_validate(config['bindings'])
        if any(config.get(key) != value for key, value in legacy_projection(result).items()):
            raise ValueError('Bindings disagree with the saved flat configuration')
        return result
    return _bindings_from_flat(config, managed_snapshot=True)


def _bindings_from_flat(config, *, managed_snapshot):
    # The old managed runner used truthiness when projecting models into env;
    # direct legacy CLI reads preserved empty strings. Keep those paths distinct.
    planner_model = config['planner_model']
    implementer_model = config['implementer_model']
    fallback_model = config['planner_fallback_model']
    if managed_snapshot:
        planner_model = planner_model or fallback_model
        implementer_model = implementer_model or DEFAULT_AGY_MODEL
        fallback_model = planner_model
    planner = _legacy_binding(config['planner'], 'planner', planner_model)
    implementer = _legacy_binding(config['implementer'], 'implementer', implementer_model)
    return AgentBindings(
        planner=planner, implementer=implementer,
        reviewer=_legacy_binding(config['reviewer'], 'reviewer'),
        planner_fallback=RoleBinding(adapter='antigravity', model=fallback_model, permission='read_only')
        if planner.adapter == 'claude_code' else None,
        agent_timeout=config['agent_timeout'],
    )


def validate_bindings(config: AgentBindings, registry):
    """Validate current adapters without enabling future CLI roles/permissions.

    Only the exact preexisting Claude/Antigravity editing bindings are retained
    despite their unverified manifests. New executors must be verified. Workflow
    validation in WF-001 will enforce its own stricter verification rules.
    """
    config = AgentBindings.model_validate(config.model_dump())
    for role, binding in [('planner', config.planner), ('implementer', config.implementer),
                          ('reviewer', config.reviewer), ('planner_fallback', config.planner_fallback)]:
        if binding is None:
            continue
        try:
            provider = registry.get(binding.adapter)
        except KeyError as exc:
            raise ValueError(f'Unsupported agent provider for {role}: {binding.adapter}') from exc
        manifest = provider.manifest
        required = {'planner': Capability.PLANNING, 'planner_fallback': Capability.PLANNING,
                    'implementer': Capability.CODE_EDIT, 'reviewer': Capability.REVIEW}[role]
        if manifest.kind != 'agent_runtime' or not {Capability.TEXT, required}.issubset(manifest.capabilities):
            raise ValueError(f'Provider lacks required capabilities for {role}')
        if binding.permission not in manifest.permission_modes:
            raise ValueError(f'Provider does not support permission for {role}')
        legacy_edit = binding.adapter in ('claude_code', 'antigravity') and role == 'implementer'
        if required == Capability.CODE_EDIT and not manifest.verified and not legacy_edit:
            raise ValueError('New code_edit runtimes must be verified')
        if role in ('planner', 'planner_fallback', 'reviewer') and binding.permission != 'read_only':
            if not (role == 'planner' and binding.adapter == 'claude_code' and binding.permission == 'workspace_write'):
                raise ValueError(f'{role} requires read_only permission')
        if role == 'implementer' and binding.permission != 'workspace_write':
            raise ValueError('implementer requires workspace_write permission')
        if binding.adapter in ('claude_code', 'codex_cli') and binding.model is not None:
            raise ValueError('Model selection unsupported by this legacy CLI adapter')
    if config.planner_fallback is not None and not (
        config.planner.adapter == 'claude_code' and config.planner_fallback.adapter == 'antigravity'
        and config.planner_fallback.permission == 'read_only'
    ):
        raise ValueError('Configurable fallbacks belong to WF-010; only the legacy fallback is supported')
    return config
