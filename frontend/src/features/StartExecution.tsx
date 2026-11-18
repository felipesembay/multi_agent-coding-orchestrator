import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Play, RefreshCw } from 'lucide-react'
import { Button } from '../components/ui/button'
import { Loading } from '../components/shared'
import { request } from '../lib/api'
import { mutate } from '../lib/projects'
import type {
  ExecutionPreflight,
  Project,
  ProjectRequest,
  StartRunResult,
  ProviderConfig,
  SavedWorkflow,
  WorkflowBinding,
  WorkflowPreset,
  WorkflowSelection,
  WorkflowVersion,
} from '../types'
import { compatibleProvider, ownBinding, permissionFor } from '../lib/workflows'

export function StartExecution({
  project,
  task,
  onClose,
}: {
  project: Project
  task: ProjectRequest
  onClose: () => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const navigate = useNavigate(),
    cache = useQueryClient()
  const [key] = useState(() => crypto.randomUUID())
  const [consent, setConsent] = useState<string | null>(null)
  const [choice, setChoice] = useState<string | null>(null)
  const [versionId, setVersionId] = useState<string | null>(null)
  const [overrides, setOverrides] = useState<Record<string, WorkflowBinding>>(
    {},
  )
  const presets = useQuery({
    queryKey: ['workflow-presets'],
    queryFn: ({ signal }) =>
      request<WorkflowPreset[]>('/workflow-presets', signal),
    retry: false,
  })
  const workflows = useQuery({
    queryKey: ['workflows'],
    queryFn: ({ signal }) => request<SavedWorkflow[]>('/workflows', signal),
    retry: false,
  })
  const providers = useQuery({
    queryKey: ['provider-configs'],
    queryFn: ({ signal }) =>
      request<ProviderConfig[]>('/provider-configs', signal),
    retry: false,
  })
  const defaultPreset = presets.data?.find((preset) => preset.default_for_ui)
  const selectedChoice =
    choice ??
    (defaultPreset?.available ? `preset:${defaultPreset.id}` : 'legacy-v1')
  const legacy = selectedChoice === 'legacy-v1'
  const preset = presets.data?.find(
    (item) => selectedChoice === `preset:${item.id}`,
  )
  const clone = useMutation({
    mutationFn: ({
      presetId,
    }: {
      presetId: string
      bindings: Record<string, WorkflowBinding>
    }) => mutate<SavedWorkflow>('/workflows', { preset_id: presetId }),
    onSuccess: async (saved, selected) => {
      // GET /workflows has definition metadata, not per-run suggestions. Keep
      // the chosen trio/models independent of the subsequent list refresh.
      setOverrides({ ...saved.suggested_bindings, ...selected.bindings })
      setChoice(`workflow:${saved.id}`)
      setVersionId(saved.latest_version?.id ?? null)
      setConsent(null)
      await cache.invalidateQueries({ queryKey: ['workflows'] })
    },
  })
  const saved =
    workflows.data?.find((item) => selectedChoice === `workflow:${item.id}`) ??
    (selectedChoice === `workflow:${clone.data?.id}` ? clone.data : undefined)
  const versions = useQuery({
    queryKey: ['workflow-versions', saved?.id],
    queryFn: ({ signal }) =>
      request<WorkflowVersion[]>(`/workflows/${saved!.id}/versions`, signal),
    enabled: !!saved,
  })
  const version = versionId
    ? (versions.data?.find((item) => item.id === versionId) ??
      (saved?.latest_version?.id === versionId
        ? saved.latest_version
        : undefined))
    : saved?.latest_version
  const definition = version?.definition ?? preset?.workflow?.definition
  const agentSteps = definition?.steps.filter((step) => step.role) ?? []
  const bindings: Record<string, WorkflowBinding> = Object.create(null)
  for (const step of agentSteps) {
    const options = (providers.data ?? []).filter((config) =>
      compatibleProvider(step, config),
    )
    const hint =
      ownBinding(preset?.suggested_bindings, step.id) ??
      ownBinding(saved?.suggested_bindings, step.id)
    const preferred =
      options.find((config) => config.id === hint?.provider_config_id) ??
      options[0]
    const binding =
      ownBinding(overrides, step.id) ??
      (preferred
        ? {
            provider_config_id: preferred.id,
            model: hint?.model ?? null,
            permission: permissionFor(step),
          }
        : null)
    if (
      binding &&
      options.some((config) => config.id === binding.provider_config_id)
    )
      bindings[step.id] = binding
  }
  const selection: WorkflowSelection | null = version
    ? { workflow_version_id: version.id, bindings }
    : null
  const canPreflight =
    !presets.isPending &&
    (legacy || (!!version && agentSteps.every((step) => !!bindings[step.id])))
  const config = useQuery({
    queryKey: ['execution-config', project.id, legacy ? null : selection],
    queryFn: ({ signal }) =>
      legacy
        ? request<ExecutionPreflight>(
            `/projects/${project.id}/execution-config`,
            signal,
          )
        : mutate<ExecutionPreflight>(
            `/projects/${project.id}/execution-config`,
            { workflow: selection },
          ),
    enabled: canPreflight,
    refetchInterval: 5000,
    staleTime: 0,
  })
  const start = useMutation({
    mutationFn: () =>
      mutate<StartRunResult>(
        `/projects/${project.id}/requests/${task.id}/runs`,
        {
          confirmed: true,
          configuration_digest: config.data?.configuration_digest,
          idempotency_key: key,
          ...(!legacy && selection ? { workflow: selection } : {}),
        },
      ),
    onSuccess: async (run) => {
      await cache.invalidateQueries({ queryKey: ['project-runs', project.id] })
      navigate(`/executions/${encodeURIComponent(run.run_id)}`)
    },
  })
  useEffect(() => {
    const current = dialog.current
    const previous = document.activeElement as HTMLElement | null
    current?.showModal()
    return () => {
      current?.close()
      previous?.focus()
    }
  }, [])
  const data = config.data
  return (
    <dialog
      ref={dialog}
      className="execution-dialog"
      aria-labelledby="execution-confirm-title"
      onCancel={(event) => {
        event.preventDefault()
        if (!start.isPending) onClose()
      }}
    >
      <div className="section-title">
        <div>
          <h2 id="execution-confirm-title">Iniciar execução real</h2>
          <p>
            Os agentes poderão modificar arquivos na worktree e consumir quotas.
          </p>
        </div>
      </div>
      <div className="request-form">
        <dl className="metadata compact">
          <div>
            <dt>Projeto</dt>
            <dd>{project.name}</dd>
          </div>
          <div>
            <dt>Solicitação existente</dt>
            <dd>{task.title}</dd>
          </div>
          <div className="wide">
            <dt>Repositório</dt>
            <dd className="mono">{project.repo_path}</dd>
          </div>
        </dl>
        <details className="test-output">
          <summary>Requisitos que serão executados</summary>
          <p className="preserve">{task.content}</p>
        </details>
        <label>
          Workflow
          <select
            aria-label="Workflow"
            value={selectedChoice}
            disabled={start.isPending || clone.isPending}
            onChange={(event) => {
              setChoice(event.target.value)
              setVersionId(null)
              setOverrides({})
              setConsent(null)
              start.reset()
            }}
          >
            <option value="legacy-v1">
              Legacy v1 — configuração atual do servidor
            </option>
            {(presets.data ?? [])
              .filter((item) => item.id !== 'legacy-v1')
              .map((item) => (
                <option
                  key={item.id}
                  value={`preset:${item.id}`}
                  disabled={!item.available}
                >
                  {item.title}
                  {!item.available ? ' (indisponível)' : ''}
                </option>
              ))}
            {(workflows.data ?? [])
              .filter((item) => item.latest_version)
              .map((item) => (
                <option key={item.id} value={`workflow:${item.id}`}>
                  {item.name}
                </option>
              ))}
            {saved && !workflows.data?.some((item) => item.id === saved.id) && (
              <option value={`workflow:${saved.id}`}>{saved.name}</option>
            )}
          </select>
        </label>
        {defaultPreset && !defaultPreset.available && (
          <p role="status" className="form-footnote">
            O padrão Claude → Codex → Antigravity está indisponível neste
            ambiente. Use o fluxo legado ou um workflow compatível.
          </p>
        )}
        {presets.error && (
          <p role="status" className="form-footnote">
            Catálogo indisponível. O fluxo legado continua disponível.
          </p>
        )}
        {preset && (
          <>
            <p>
              Será criada uma cópia editável de {preset.title}; nenhum agente
              será executado nesta etapa.
            </p>
            <Button
              disabled={!preset.available || clone.isPending || start.isPending}
              onClick={() =>
                clone.mutate({
                  presetId: preset.id,
                  bindings: Object.fromEntries(
                    Object.entries(bindings).map(([id, binding]) => [
                      id,
                      { ...binding },
                    ]),
                  ),
                })
              }
            >
              {clone.isPending ? 'Preparando preset…' : 'Usar este preset'}
            </Button>
          </>
        )}
        {version && (
          <label>
            Versão do workflow
            <select
              aria-label="Versão do workflow"
              value={version.id}
              disabled={start.isPending}
              onChange={(event) => {
                setVersionId(event.target.value)
                setOverrides({})
                setConsent(null)
              }}
            >
              {(versions.data ?? [version]).map((item) => (
                <option key={item.id} value={item.id}>
                  Versão {item.version}
                </option>
              ))}
            </select>
          </label>
        )}
        {!legacy &&
          agentSteps.map((step) => {
            const options = (providers.data ?? []).filter((config) =>
              compatibleProvider(step, config),
            )
            const binding = bindings[step.id]
            const provider = options.find(
              (item) => item.id === binding?.provider_config_id,
            )
            return (
              <fieldset
                key={step.id}
                disabled={start.isPending || clone.isPending}
              >
                <legend>
                  {step.id} · {step.role}
                </legend>
                <label>
                  Provider para {step.id}
                  <select
                    aria-label={`Provider para ${step.id}`}
                    value={binding?.provider_config_id ?? ''}
                    onChange={(event) => {
                      setOverrides((previous) => ({
                        ...previous,
                        [step.id]: {
                          provider_config_id: event.target.value,
                          model: null,
                          permission: permissionFor(step),
                        },
                      }))
                      setConsent(null)
                    }}
                  >
                    <option value="">Selecione um provider compatível</option>
                    {options.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.display_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Modelo para {step.id}
                  <input
                    aria-label={`Modelo para ${step.id}`}
                    value={binding?.model ?? ''}
                    maxLength={256}
                    disabled={!provider?.model_selection}
                    placeholder="Modelo padrão do provider"
                    onChange={(event) => {
                      if (binding)
                        setOverrides((previous) => ({
                          ...previous,
                          [step.id]: {
                            ...binding,
                            model: event.target.value || null,
                          },
                        }))
                      setConsent(null)
                    }}
                  />
                </label>
                {!provider?.model_selection && provider && (
                  <p className="form-footnote">
                    Este adapter utiliza o modelo padrão do CLI.
                  </p>
                )}
                {!options.length && (
                  <p className="form-error">
                    Nenhum provider compatível está configurado para esta etapa.
                  </p>
                )}
              </fieldset>
            )
          })}
        {[workflows.error, providers.error, versions.error, clone.error]
          .filter(Boolean)
          .map((error, index) => (
            <p key={index} role="alert" className="form-error">
              {error?.message}
            </p>
          ))}
        {!canPreflight ? (
          <p className="form-footnote">
            Escolha um workflow e providers compatíveis para revisar a execução.
          </p>
        ) : config.isPending ? (
          <Loading />
        ) : (
          data && (
            <>
              <dl className="settings-list">
                <div>
                  <dt>Planner</dt>
                  <dd>
                    {data.configuration.planner} ·{' '}
                    {data.configuration.planner_model ?? 'modelo padrão do CLI'}
                  </dd>
                </div>
                {legacy && data.configuration.planner === 'claude' && (
                  <div>
                    <dt>Fallback por limite do planner</dt>
                    <dd>
                      Antigravity · {data.configuration.planner_fallback_model}
                    </dd>
                  </div>
                )}
                <div>
                  <dt>Implementer</dt>
                  <dd>
                    {data.configuration.implementer} ·{' '}
                    {data.configuration.implementer_model ??
                      'modelo padrão do CLI'}
                  </dd>
                </div>
                <div>
                  <dt>Reviewer</dt>
                  <dd>
                    {data.configuration.reviewer} ·{' '}
                    {legacy
                      ? 'modelo padrão do CLI'
                      : 'modelo selecionado na etapa'}
                  </dd>
                </div>
                <div>
                  <dt>Comando de testes</dt>
                  <dd className="mono">
                    {data.configuration.test_command || 'Não configurado'}
                  </dd>
                </div>
                <div>
                  <dt>Tentativas por tarefa</dt>
                  <dd>{data.configuration.max_attempts}</dd>
                </div>
                <div>
                  <dt>Worker</dt>
                  <dd
                    className={data.worker.online ? 'text-green' : 'text-amber'}
                  >
                    {data.worker.online ? 'Online' : 'Offline'}
                  </dd>
                </div>
              </dl>
              {data.errors.length > 0 && (
                <div className="form-error" role="alert">
                  <strong>Resolva antes de iniciar:</strong>
                  <ul>
                    {data.errors.map((error) => (
                      <li key={error}>{error}</li>
                    ))}
                  </ul>
                </div>
              )}
              <label className="confirmation-checkbox">
                <input
                  type="checkbox"
                  checked={
                    canPreflight && consent === data.configuration_digest
                  }
                  disabled={
                    !canPreflight ||
                    !data.ready ||
                    start.isPending ||
                    config.isFetching
                  }
                  onChange={(event) =>
                    setConsent(
                      event.target.checked ? data.configuration_digest : null,
                    )
                  }
                />
                <span>
                  Confirmo a execução destes requisitos com os agentes e o
                  comando de testes exibidos.
                </span>
              </label>
            </>
          )
        )}
        {config.error && (
          <p role="alert" className="form-error">
            {config.error.message}
          </p>
        )}
        {start.error && (
          <p role="alert" className="form-error">
            {start.error.message}
          </p>
        )}
        <p className="form-footnote">
          A configuração confirmada será congelada para esta execução. O
          resultado ficará para análise humana. Nenhum merge, push ou deploy
          será realizado.
        </p>
        <div className="form-actions">
          <Button disabled={start.isPending} onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={start.isPending || config.isFetching || !canPreflight}
            aria-label="Atualizar verificações"
            onClick={() => void config.refetch()}
          >
            <RefreshCw size={14} />
          </Button>
          <Button
            variant="default"
            disabled={
              !canPreflight ||
              config.isFetching ||
              !data?.ready ||
              consent !== data?.configuration_digest ||
              start.isPending
            }
            onClick={() => start.mutate()}
          >
            <Play size={14} />
            {start.isPending ? 'Registrando execução…' : 'Confirmar e iniciar'}
          </Button>
        </div>
      </div>
    </dialog>
  )
}
