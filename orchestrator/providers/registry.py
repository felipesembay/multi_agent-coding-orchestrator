"""Built-ins plus explicitly enabled, installed entry points; never invokes agents."""
from importlib import metadata
import re
from typing import Iterable, Literal, Optional

from pydantic import BaseModel

from .base import CapabilityManifest, ProbeResult
from ..policy.env import INTERNAL_SCOPES
from .runtimes.antigravity import AntigravityRuntime
from .runtimes.claude_code import ClaudeCodeRuntime
from .runtimes.codex_cli import CodexCliRuntime
from .models.openrouter import OpenRouterProvider


BUILTINS = {
    'claude_code': ClaudeCodeRuntime,
    'codex_cli': CodexCliRuntime,
    'antigravity': AntigravityRuntime,
    'openrouter': lambda runner, observer=None: OpenRouterProvider(),
}


def _unconfigured_runner(*args, **kwargs):
    raise RuntimeError('Provider execution runner not configured')


class ProviderInfo(BaseModel):
    adapter: str
    source: Literal['builtin', 'entry_point']
    manifest: Optional[CapabilityManifest] = None
    probe: ProbeResult


class ProviderRegistry:
    """Plugins export a zero-argument factory returning a provider instance.

    Opt-in is trusted process configuration, never an HTTP parameter. The future
    provider_configs integration must pass only explicitly enabled adapters.
    Built-ins may receive an execution runner/observer for later workflow use.
    """

    def __init__(self, *, enabled_entry_points: Iterable[str] = (),
                 runner=_unconfigured_runner, observer=None):
        if isinstance(enabled_entry_points, str):
            raise ValueError('enabled_entry_points must be a collection of names')
        enabled = set(enabled_entry_points)
        if any(not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', name) for name in enabled):
            raise ValueError('Invalid entry point name')
        if enabled.intersection(INTERNAL_SCOPES):
            raise ValueError('An entry point cannot use an internal policy scope')
        if enabled.intersection(BUILTINS):
            raise ValueError('An entry point cannot replace a built-in provider')
        self._providers = {name: factory(runner, observer=observer) for name, factory in BUILTINS.items()}
        self._failures = {}
        if not enabled:
            return  # Do not even discover/import third-party packages by default.
        try:
            found = metadata.entry_points()
            entries = found.select(group='orchestrator.providers') if hasattr(found, 'select') else found.get('orchestrator.providers', ())
            selected = {name: [] for name in enabled}
            for entry in entries:
                if entry.name in selected:
                    selected[entry.name].append(entry)
        except Exception:
            self._failures.update({name: 'load_failed' for name in enabled})
            return
        for name in sorted(enabled):
            matches = selected[name]
            if len(matches) != 1:
                self._failures[name] = 'duplicate_entry_point' if matches else 'entry_point_missing'
                continue
            try:
                provider = matches[0].load()()
            except Exception:
                self._failures[name] = 'load_failed'
                continue
            try:
                manifest = self._manifest(provider, name)
                required = ('invoke',) if manifest.kind == 'agent_runtime' else ('generate', 'list_models')
                if not callable(getattr(provider, 'probe', None)) or not all(callable(getattr(provider, method, None)) for method in required):
                    raise ValueError('Invalid provider interface')
            except Exception:
                self._failures[name] = 'invalid_provider'
                continue
            self._providers[name] = provider

    @staticmethod
    def _manifest(provider, name):
        raw = provider.manifest
        manifest = CapabilityManifest.model_validate(raw.model_dump() if isinstance(raw, CapabilityManifest) else raw)
        if manifest.adapter != name:
            raise ValueError('Provider identity mismatch')
        return manifest

    def get(self, adapter):
        return self._providers[adapter]

    def list(self) -> list[ProviderInfo]:
        rows = []
        for name in sorted(set(self._providers) | set(self._failures)):
            source = 'builtin' if name in BUILTINS else 'entry_point'
            if name in self._failures:
                rows.append(ProviderInfo(adapter=name, source=source,
                                         probe=ProbeResult(error_code=self._failures[name])))
                continue
            provider = self._providers[name]
            try:
                manifest = self._manifest(provider, name)
            except Exception:
                rows.append(ProviderInfo(adapter=name, source=source,
                                         probe=ProbeResult(error_code='invalid_provider')))
                continue
            try:
                raw = provider.probe()
                probe = ProbeResult.model_validate(raw.model_dump() if isinstance(raw, ProbeResult) else raw)
            except Exception:
                probe = ProbeResult(error_code='probe_failed')
            rows.append(ProviderInfo(adapter=name, source=source, manifest=manifest, probe=probe))
        return rows


def get_provider_registry() -> ProviderRegistry:
    # No provider_configs table until WF-002. Third-party plugins stay disabled.
    return ProviderRegistry()
