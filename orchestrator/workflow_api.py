"""Authenticated workflow catalog/selection; handlers never invoke agents."""
import json
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError, model_validator

from .project_store import connection
from .projects import ProjectError, audit
from .providers.base import CapabilityManifest
from .providers.registry import ProviderRegistry, get_provider_registry
from .workflows import store
from .workflows.presets import clone_preset, get_preset, list_presets
from .workflows.schema import Identifier, StepBinding, WorkflowDefinition
from .workflows.snapshot import WorkflowSnapshot, WorkflowSnapshotError, resolve_providers, validate_snapshot
from .workflows.validation import validate_workflow

router = APIRouter()


def field_errors(error):
    return [{key: item[key] for key in ('loc', 'msg', 'type')} for item in error.errors()]


class VersionInput(BaseModel):
    model_config = {'extra': 'forbid'}
    definition: WorkflowDefinition


class CreateInput(BaseModel):
    model_config = {'extra': 'forbid'}
    definition: Optional[WorkflowDefinition] = None
    preset_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, min_length=1, max_length=120, pattern=r'\S')
    description: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def one_source(self):
        if (self.definition is None) == (self.preset_id is None):
            raise ValueError('Choose definition or preset_id')
        return self


class ValidateInput(VersionInput):
    bindings: Optional[dict[str, StepBinding]] = None


class ProviderInput(BaseModel):
    model_config = {'extra': 'forbid'}
    adapter: Identifier
    display_name: str = Field(min_length=1, max_length=120)


def manifest(registry, adapter):
    raw = registry.get(adapter).manifest
    value = CapabilityManifest.model_validate(raw.model_dump() if isinstance(raw, CapabilityManifest) else raw)
    if value.adapter != adapter:
        raise ValueError('Provider identity mismatch')
    return value


def provider_configs(registry):
    with connection() as conn:
        rows = conn.execute('SELECT * FROM provider_configs ORDER BY display_name,id').fetchall()
    result = []
    for row in rows:
        info = dict(id=row['id'], kind=row['kind'], adapter=row['adapter'], display_name=row['display_name'],
                    enabled=bool(row['enabled']), available=False, capabilities=[], permission_modes=[], verified=False,
                    model_selection=row['adapter'] not in ('claude_code', 'codex_cli'))
        try:
            declared = manifest(registry, row['adapter'])
            info.update(capabilities=sorted(c.value for c in declared.capabilities),
                        permission_modes=declared.permission_modes, verified=declared.verified,
                        available=bool(row['enabled'] and declared.kind == row['kind'] == 'agent_runtime'
                                       and json.loads(row['settings']) == {} and row['credential_ref'] is None))
        except Exception:
            pass  # Unavailable adapter never exposes plugin exception payloads.
        result.append(info)
    return result


def suggested(workflow, configs):
    result = {}
    for step_id, binding in workflow.bindings.items():
        adapter = workflow.provider_configs[binding.provider_config_id]
        config = next((p for p in configs if p['adapter'] == adapter and p['available']), None)
        if config:
            result[step_id] = {**binding.model_dump(mode='json'), 'provider_config_id': config['id']}
    return result


@router.get('/provider-configs')
def get_configs(registry: ProviderRegistry = Depends(get_provider_registry)):
    return provider_configs(registry)


@router.post('/provider-configs', status_code=201)
def create_config(data: ProviderInput, registry: ProviderRegistry = Depends(get_provider_registry)):
    try:
        declared = manifest(registry, data.adapter)
    except Exception:
        raise ProjectError('Adapter não registrado no servidor.', 422) from None
    key = 'pc-' + uuid.uuid4().hex
    with connection() as conn:
        conn.execute('INSERT INTO provider_configs(id,kind,adapter,display_name,enabled) VALUES(?,?,?,?,1)',
                     (key, declared.kind, data.adapter, data.display_name))
        audit(conn, 'provider.configured', None, provider_config_id=key, adapter=data.adapter)
        conn.commit()
    return next(p for p in provider_configs(registry) if p['id'] == key)


@router.get('/workflow-presets')
def presets(registry: ProviderRegistry = Depends(get_provider_registry)):
    configs = provider_configs(registry)
    result = []
    for preset in list_presets():
        data = preset.model_dump(mode='json')
        data.update(default_for_ui=preset.id == 'default-v2', default_for_cli=preset.id == 'legacy-v1',
                    suggested_bindings={}, available=preset.execution_mode == 'legacy', errors=[])
        if preset.workflow is not None:
            hints = suggested(preset.workflow, configs)
            data['suggested_bindings'] = hints
            if preset.blocked_by:
                data['errors'] = ['Integração pendente: ' + ', '.join(preset.blocked_by)]
            elif set(hints) != set(preset.workflow.bindings):
                data['errors'] = ['Configure providers locais compatíveis para todas as etapas.']
            else:
                try:
                    resolved = resolve_providers({key: StepBinding.model_validate(value) for key, value in hints.items()})
                    validate_snapshot(WorkflowSnapshot(workflow_version_id='preset-preview',
                        definition=preset.workflow.definition, bindings=hints, providers=resolved), registry=registry)
                    data['available'] = True
                except ValueError:
                    data['errors'] = ['Capacidades ou permissões do preset ainda indisponíveis.']
        result.append(data)
    return result


@router.get('/workflows')
def workflows():
    return store.list_workflows()


@router.post('/workflows', status_code=201)
def create_workflow(data: CreateInput, registry: ProviderRegistry = Depends(get_provider_registry)):
    draft = None
    if data.preset_id is not None:
        try:
            preset = get_preset(data.preset_id)
        except ValueError:
            raise ProjectError('Preset não encontrado.', 404) from None
        if preset.blocked_by:
            raise ProjectError('Integração do preset ainda pendente.', 409)
        try:
            draft = clone_preset(data.preset_id, name=data.name or preset.title)
        except ValueError:
            raise ProjectError('Configuração do preset inválida no servidor.', 422) from None
        definition = draft.definition
    else:
        definition = data.definition
        if data.name is not None:
            definition = WorkflowDefinition.model_validate({**definition.model_dump(), 'name': data.name})
    result = store.create_workflow(definition, data.description)
    result['suggested_bindings'] = suggested(draft, provider_configs(registry)) if draft else {}
    return result


@router.get('/workflows/{workflow_id}/versions')
def versions(workflow_id: str):
    return store.versions(workflow_id)


@router.post('/workflows/{workflow_id}/versions', status_code=201)
def append(workflow_id: str, data: VersionInput):
    workflow = store.get_workflow(workflow_id)
    if workflow['read_only']:
        raise ProjectError('Preset do sistema é somente leitura; crie uma cópia.', 403)
    key = store.append_version(workflow_id, data.definition)
    return next(row for row in store.versions(workflow_id) if row['id'] == key)


@router.post('/workflows/validate')
def validate(data: ValidateInput, registry: ProviderRegistry = Depends(get_provider_registry)):
    if data.bindings is None:
        # Pydantic already checked the whole definition/topology. Binding and
        # execution checks remain mandatory in the run confirmation path.
        return {'valid': True, 'executable': None, 'errors': [], 'validation_scope': 'definition'}
    providers = resolve_providers(data.bindings)
    try:
        validate_workflow(data.definition, data.bindings,
                          provider_configs={key: p.adapter for key, p in providers.items()}, registry=registry)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=field_errors(error)) from None
    errors = []
    try:
        validate_snapshot(WorkflowSnapshot(workflow_version_id='validation', definition=data.definition,
                                          bindings=data.bindings, providers=providers), registry=registry)
    except WorkflowSnapshotError as error:
        errors.append(str(error))
    return {'valid': True, 'executable': not errors, 'errors': errors}
