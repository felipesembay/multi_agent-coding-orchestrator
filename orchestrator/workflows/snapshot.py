"""Frozen execution selections; dispatch never rereads mutable provider records."""
from contextlib import nullcontext
import hashlib
import json
import os
from typing import Literal

from pydantic import BaseModel, Field, model_serializer, model_validator

from ..project_store import connection
from ..providers.base import CapabilityManifest, GenerationRequest
from ..secrets.store import format_credential_ref
from ..providers.bindings import DEFAULT_AGY_MODEL
from .schema import Identifier, StepBinding, WorkflowDefinition
from .validation import validate_workflow


class WorkflowSnapshotError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class WorkflowSelection(BaseModel):
    model_config = {'extra': 'forbid'}
    workflow_version_id: Identifier
    bindings: dict[str, StepBinding]


class FrozenProvider(BaseModel):
    model_config = {'extra': 'forbid', 'frozen': True}
    adapter: Identifier
    kind: Literal['agent_runtime', 'model_provider']
    credential_ref: str | None = None

    @model_serializer(mode='wrap')
    def legacy_shape(self, handler):
        value = handler(self)
        if self.credential_ref is None:
            value.pop('credential_ref', None)
        return value


class WorkflowSnapshot(WorkflowSelection):
    model_config = {'extra': 'forbid', 'frozen': True}
    schema_version: int = Field(default=1, strict=True, ge=1, le=1)
    definition: WorkflowDefinition
    providers: dict[str, FrozenProvider]

    @model_validator(mode='after')
    def referenced_providers(self):
        if {b.provider_config_id for b in binding_candidates(self.bindings)} != set(self.providers):
            raise ValueError('Snapshot providers must match the referenced configurations')
        return self

    def digest(self):
        return digest(self.model_dump(mode='json'))


def binding_candidates(bindings):
    """All configured alternatives, including ones not selected on this run."""
    for binding in bindings.values():
        yield binding
        yield from binding.fallbacks


def validate_snapshot(snapshot, *, registry):
    """Reparse copies and recheck installed capabilities; never enable plugins."""
    try:
        parsed = WorkflowSnapshot.model_validate(
            snapshot.model_dump(mode='json') if isinstance(snapshot, WorkflowSnapshot) else snapshot)
        definition = parsed.definition
        if (definition.approval.human_gate_after_plan
                or any(s.type == 'human_gate' for s in definition.steps)):
            raise WorkflowSnapshotError('Human gates require the approvals integration')
        if definition.limits.budget_usd is not None:
            raise WorkflowSnapshotError('Budgets require the accounting integration')
        if any(b.parameters for b in binding_candidates(parsed.bindings)):
            raise WorkflowSnapshotError('Runtime parameters are not integrated yet')
        if any(parsed.providers[b.provider_config_id].adapter in ('claude_code', 'codex_cli') and b.model is not None
               for b in binding_candidates(parsed.bindings)):
            raise WorkflowSnapshotError('Selected CLI adapter does not support explicit models yet')
        for config_id, provider in parsed.providers.items():
            if provider.kind == 'model_provider':
                if provider.adapter != 'openrouter' or provider.credential_ref != format_credential_ref('openrouter', config_id):
                    raise WorkflowSnapshotError('Model provider requires a supported keyring reference')
                for binding in binding_candidates(parsed.bindings):
                    if binding.provider_config_id == config_id:
                        GenerationRequest(role='planner', prompt='', model=binding.model,
                                          credential_ref=provider.credential_ref, permission=binding.permission)
            elif provider.credential_ref is not None:
                raise WorkflowSnapshotError('CLI credentials are managed by the CLI')
            raw = registry.get(provider.adapter).manifest
            manifest = CapabilityManifest.model_validate(raw.model_dump() if isinstance(raw, CapabilityManifest) else raw)
            if manifest.kind != provider.kind:
                raise WorkflowSnapshotError('Provider kind changed')
        validate_workflow(definition, parsed.bindings,
                          provider_configs={key: p.adapter for key, p in parsed.providers.items()}, registry=registry)
        parsed.digest()  # Also reject non-finite JSON parameters.
        return parsed
    except WorkflowSnapshotError:
        raise
    except Exception:
        raise WorkflowSnapshotError('Invalid workflow snapshot or unavailable provider') from None


def load_snapshot(selection, *, registry, conn=None):
    """Resolve an immutable version and enabled, supported server configurations.

    No settings/credential values enter the snapshot. Nonempty settings and
    credential references are refused until their invocation integration exists.
    """
    try:
        selection = WorkflowSelection.model_validate(
            selection.model_dump(mode='json') if isinstance(selection, WorkflowSelection) else selection)
        with nullcontext(conn) if conn is not None else connection() as owned:
            version = owned.execute('''SELECT v.*,d.archived_at FROM workflow_versions v
                JOIN workflow_definitions d ON d.id=v.definition_id WHERE v.id=?''',
                                    (selection.workflow_version_id,)).fetchone()
            if version is None or version['archived_at'] is not None:
                raise WorkflowSnapshotError('Workflow version missing or archived')
            definition = WorkflowDefinition.model_validate_json(version['body'])
            if (version['schema_version'] != definition.schema_version
                    or version['digest'] != digest(definition.model_dump(mode='json'))):
                raise WorkflowSnapshotError('Workflow version integrity check failed')
            providers = resolve_providers(selection.bindings, conn=owned)
            # This adapter has a known environment-based model default. Resolve
            # it here so worker environment drift cannot change a confirmed run.
            for binding in binding_candidates(selection.bindings):
                if providers[binding.provider_config_id].adapter == 'antigravity' and binding.model is None:
                    binding.model = type(binding).model_validate({**binding.model_dump(),
                        'model': os.getenv('ORCH_ANTIGRAVITY_MODEL', DEFAULT_AGY_MODEL)}).model
            return validate_snapshot(WorkflowSnapshot(**selection.model_dump(), definition=definition,
                                                      providers=providers), registry=registry)
    except WorkflowSnapshotError:
        raise
    except Exception:
        raise WorkflowSnapshotError('Invalid workflow selection or version') from None


def resolve_providers(bindings, *, conn=None):
    with nullcontext(conn) if conn is not None else connection() as owned:
        providers = {}
        for config_id in sorted({b.provider_config_id for b in binding_candidates(bindings)}):
            row = owned.execute('SELECT * FROM provider_configs WHERE id=?', (config_id,)).fetchone()
            if row is None or not row['enabled']:
                raise WorkflowSnapshotError('Provider configuration missing or disabled')
            if json.loads(row['settings']) != {}:
                raise WorkflowSnapshotError('Provider settings or credentials require integration')
            ref = row['credential_ref']
            if row['kind'] == 'model_provider':
                if row['adapter'] != 'openrouter' or ref != format_credential_ref('openrouter', config_id):
                    raise WorkflowSnapshotError('Model provider requires a supported keyring reference')
            elif ref is not None:
                raise WorkflowSnapshotError('CLI credentials are managed by the CLI')
            providers[config_id] = FrozenProvider(adapter=row['adapter'], kind=row['kind'], credential_ref=ref)
        return providers


def verify_run_snapshot(row, config):
    """Check dedicated columns against the exact config payload, without DB lookup."""
    raw = config.get('workflow')
    if raw is None:
        if any(row.get(key) is not None for key in ('workflow_version_id', 'bindings', 'workflow_digest')):
            raise WorkflowSnapshotError('Unpaired workflow metadata')
        return None
    try:
        snapshot = WorkflowSnapshot.model_validate(raw)
        if (row.get('workflow_version_id') != snapshot.workflow_version_id
                or row.get('workflow_digest') != snapshot.digest()
                or json.loads(row['bindings']) != snapshot.model_dump(mode='json')['bindings']):
            raise WorkflowSnapshotError('Run workflow snapshot integrity check failed')
        return snapshot
    except WorkflowSnapshotError:
        raise
    except Exception:
        raise WorkflowSnapshotError('Invalid run workflow snapshot') from None
