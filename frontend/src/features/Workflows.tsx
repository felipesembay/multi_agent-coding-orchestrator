import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Link,
  Navigate,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router-dom'
import { Button } from '../components/ui/button'
import { Loading } from '../components/shared'
import { request } from '../lib/api'
import { mutate } from '../lib/projects'
import { copyName, newDefinition } from '../lib/workflow-editor'
import type { SavedWorkflow, WorkflowPreset, WorkflowVersion } from '../types'
import { WorkflowEditor } from './WorkflowEditor'

export function WorkflowsPage() {
  const navigate = useNavigate(),
    cache = useQueryClient()
  const workflows = useQuery({
    queryKey: ['workflows'],
    queryFn: ({ signal }) => request<SavedWorkflow[]>('/workflows', signal),
  })
  const presets = useQuery({
    queryKey: ['workflow-presets'],
    queryFn: ({ signal }) =>
      request<WorkflowPreset[]>('/workflow-presets', signal),
  })
  const clone = useMutation({
    mutationFn: (preset: WorkflowPreset) =>
      mutate<SavedWorkflow>('/workflows', {
        preset_id: preset.id,
        name: copyName(preset.title),
      }),
    onSuccess: async (saved) => {
      await cache.invalidateQueries({ queryKey: ['workflows'] })
      navigate(`/workflows/${encodeURIComponent(saved.id)}`)
    },
  })
  return (
    <section className="workflow-page">
      <div className="section-title">
        <div>
          <h1>Workflows</h1>
          <p>Defina etapas e limites sem iniciar agentes.</p>
        </div>
        <Button asChild variant="default">
          <Link to="/workflows/new">Novo workflow</Link>
        </Button>
      </div>
      <h2>Presets do sistema</h2>
      <p>
        Os originais são somente leitura. Crie uma cópia para editar;
        disponibilidade de execução é verificada separadamente.
      </p>
      {presets.isPending && <Loading />}
      <div className="workflow-cards">
        {(presets.data ?? []).map((preset) => (
          <article className="panel workflow-card" key={preset.id}>
            <h3>{preset.title}</h3>
            <p>Preset do sistema · somente leitura</p>
            {!preset.available && (
              <p className="text-amber">
                {preset.errors.join(' ') || 'Execução ainda indisponível.'}
              </p>
            )}
            <Button
              disabled={clone.isPending || !!preset.blocked_by?.length}
              aria-label={`Criar cópia de ${preset.title}`}
              onClick={() => clone.mutate(preset)}
            >
              Criar cópia
            </Button>
          </article>
        ))}
      </div>
      <h2>Seus workflows</h2>
      {workflows.isPending && <Loading />}
      {workflows.data?.length === 0 && (
        <p>Nenhum workflow salvo. Crie um novo ou copie um preset.</p>
      )}
      <div className="workflow-cards">
        {(workflows.data ?? []).map((workflow) => (
          <article key={workflow.id} className="panel workflow-card">
            <h3>{workflow.name}</h3>
            <p>{workflow.description}</p>
            <p>
              {workflow.read_only ? 'Somente leitura' : 'Workflow do usuário'} ·
              versão {workflow.latest_version?.version ?? '—'}
            </p>
            <Button asChild>
              <Link to={`/workflows/${encodeURIComponent(workflow.id)}`}>
                Abrir workflow {workflow.name}
              </Link>
            </Button>
          </article>
        ))}
      </div>
      {[workflows.error, presets.error, clone.error]
        .filter(Boolean)
        .map((error, index) => (
          <p key={index} role="alert" className="form-error">
            {error?.message}
          </p>
        ))}
    </section>
  )
}

export function WorkflowEditorPage() {
  const { workflowId } = useParams()
  const [search, setSearch] = useSearchParams()
  const workflows = useQuery({
    queryKey: ['workflows'],
    queryFn: ({ signal }) => request<SavedWorkflow[]>('/workflows', signal),
    enabled: !!workflowId,
  })
  const versions = useQuery({
    queryKey: ['workflow-versions', workflowId],
    queryFn: ({ signal }) =>
      request<WorkflowVersion[]>(
        `/workflows/${encodeURIComponent(workflowId!)}/versions`,
        signal,
      ),
    enabled: !!workflowId,
  })
  if (!workflowId) return <WorkflowEditor initial={newDefinition()} />
  if (workflows.isPending || versions.isPending) return <Loading />
  const error = workflows.error ?? versions.error
  if (error && (!workflows.data || !versions.data))
    return (
      <p role="alert" className="form-error">
        {error.message}
      </p>
    )
  const workflow = workflows.data?.find((item) => item.id === workflowId)
  const requested = search.get('version')
  const version = requested
    ? versions.data?.find((item) => item.id === requested)
    : versions.data?.at(-1)
  if (!workflow || !version)
    return (
      <section>
        <h1>Workflow ou versão não encontrada</h1>
        <Link to="/workflows">Voltar aos workflows</Link>
      </section>
    )
  // Pin the base version before editing so background refreshes cannot replace a draft.
  if (!requested)
    return (
      <Navigate replace to={`?version=${encodeURIComponent(version.id)}`} />
    )
  return (
    <>
      {error && (
        <p role="alert" className="form-error">
          Não foi possível atualizar a lista. Seu rascunho foi preservado.
        </p>
      )}
      <WorkflowEditor
        key={`${workflow.id}:${version.id}`}
        workflow={workflow}
        baseVersion={version}
        versions={versions.data}
        initial={version.definition}
        onVersion={(id) => setSearch({ version: id })}
      />
    </>
  )
}
