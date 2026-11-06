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
} from '../types'

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
  const config = useQuery({
    queryKey: ['execution-config', project.id],
    queryFn: ({ signal }) =>
      request<ExecutionPreflight>(
        `/projects/${project.id}/execution-config`,
        signal,
      ),
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
        {config.isPending ? (
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
                {data.configuration.planner === 'claude' && (
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
                  <dd>Codex · modelo padrão do CLI</dd>
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
                  checked={consent === data.configuration_digest}
                  disabled={!data.ready || start.isPending}
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
          A configuração é definida no servidor. O workflow executará
          planejamento, implementação, testes e revisão automática; o resultado
          ficará para análise humana. Nenhum merge, push ou deploy será
          realizado.
        </p>
        <div className="form-actions">
          <Button disabled={start.isPending} onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={start.isPending || config.isFetching}
            aria-label="Atualizar verificações"
            onClick={() => void config.refetch()}
          >
            <RefreshCw size={14} />
          </Button>
          <Button
            variant="default"
            disabled={
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
