import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  FileText,
  FolderGit2,
  GitBranch,
  Pencil,
  Plus,
  Play,
  RefreshCw,
  Target,
} from 'lucide-react'
import { Link, useOutletContext, useParams } from 'react-router-dom'
import type { DashboardContext } from '../components/layout/Layout'
import { Button } from '../components/ui/button'
import {
  Empty,
  ErrorState,
  Loading,
  SectionTitle,
  Status,
  TestBadge,
} from '../components/shared'
import { date, duration } from '../lib/events'
import {
  mutate,
  useProject,
  useProjectRequests,
  useProjectRuns,
} from '../lib/projects'
import type { Project, ProjectRequest, Run } from '../types'
import { StartExecution } from './StartExecution'

export function ProjectWorkspacePage() {
  const { projectId = '' } = useParams(),
    { interval } = useOutletContext<DashboardContext>()
  const project = useProject(projectId),
    requests = useProjectRequests(projectId, interval),
    runs = useProjectRuns(projectId, interval)
  const client = useQueryClient()
  const [selectedRequest, setSelectedRequest] = useState<ProjectRequest | null>(
    null,
  )
  const [tab, setTab] = useState('requests'),
    [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(''),
    [content, setContent] = useState('')
  const submit = useMutation({
    mutationFn: () =>
      mutate<ProjectRequest>(`/projects/${projectId}/requests`, {
        title,
        content,
      }),
    onSuccess: async () => {
      setTitle('')
      setContent('')
      await Promise.all([
        client.invalidateQueries({ queryKey: ['project-requests', projectId] }),
        client.invalidateQueries({ queryKey: ['projects'] }),
        client.invalidateQueries({ queryKey: ['project', projectId] }),
      ])
    },
  })
  const refresh = () => {
    void project.refetch()
    void requests.refetch()
    void runs.refetch()
  }
  return (
    <>
      <Link className="back-link" to="/">
        <ArrowLeft size={14} />
        Todos os projetos
      </Link>
      {project.isError && (
        <ErrorState error={project.error} retry={project.refetch} />
      )}
      {project.isPending ? (
        <Loading />
      ) : (
        project.data && (
          <>
            <div className="page-heading">
              <div>
                <div className="eyebrow">PROJECT WORKSPACE</div>
                <h1>
                  {project.data.name}
                  <span>.</span>
                </h1>
                <p>
                  {project.data.description ||
                    'Seu espaço de desenvolvimento e acompanhamento.'}
                </p>
              </div>
              <div className="heading-actions">
                <Button aria-label="Atualizar projeto" onClick={refresh}>
                  <RefreshCw size={15} />
                </Button>
                <Button onClick={() => setEditing(!editing)}>
                  <Pencil size={14} />
                  {editing ? 'Fechar edição' : 'Editar projeto'}
                </Button>
              </div>
            </div>
            {editing && (
              <ProjectEditor
                project={project.data}
                onClose={() => setEditing(false)}
              />
            )}
            <section className="panel project-context">
              <div className="project-context-title">
                <span className="project-avatar">
                  <FolderGit2 size={25} />
                </span>
                <div>
                  <h2>{project.data.name}</h2>
                  <span className={`project-state ${project.data.state}`}>
                    {project.data.state === 'active'
                      ? 'Projeto ativo'
                      : 'Projeto arquivado'}
                  </span>
                </div>
              </div>
              <div className="project-facts">
                <div>
                  <GitBranch size={16} />
                  <span>
                    Repositório
                    <strong className="mono">{project.data.repo_path}</strong>
                  </span>
                </div>
                <div>
                  <CalendarDays size={16} />
                  <span>
                    Criado em<strong>{date(project.data.created_at)}</strong>
                  </span>
                </div>
                <div>
                  <CalendarDays size={16} />
                  <span>
                    Atualizado em
                    <strong>{date(project.data.updated_at)}</strong>
                  </span>
                </div>
              </div>
              {project.data.objectives && (
                <div className="project-objectives">
                  <h3>
                    <Target size={15} />
                    Objetivos do projeto
                  </h3>
                  <p className="preserve">{project.data.objectives}</p>
                </div>
              )}
            </section>
            {runs.data?.some((run) =>
              ['queued', 'running'].includes(run.status),
            ) && (
              <section className="panel">
                <SectionTitle title="Execução em andamento" />
                {runs.data
                  .filter((run) => ['queued', 'running'].includes(run.status))
                  .map((run) => (
                    <Link
                      className="active-execution"
                      key={run.run_id}
                      to={`/executions/${run.run_id}`}
                    >
                      <div>
                        <strong>
                          {run.request_title ?? 'Execução do repositório'}
                        </strong>
                        <p>
                          {run.current_stage ?? 'Aguardando despacho do worker'}
                        </p>
                      </div>
                      <Status status={run.status} />
                      <ArrowRight size={16} />
                    </Link>
                  ))}
              </section>
            )}
            <div className="tabs" aria-label="Seções do projeto">
              <Button
                variant="ghost"
                aria-pressed={tab === 'requests'}
                onClick={() => setTab('requests')}
              >
                Solicitações
                <span className="count">{requests.data?.length ?? '—'}</span>
              </Button>
              <Button
                variant="ghost"
                aria-pressed={tab === 'history'}
                onClick={() => setTab('history')}
              >
                Histórico do repositório
                <span className="count">{runs.data?.length ?? '—'}</span>
              </Button>
            </div>
            {tab === 'requests' ? (
              <div className="project-workspace-grid">
                <section className="panel">
                  <SectionTitle
                    title="O que vamos desenvolver?"
                    subtitle="Descreva um requisito, uma funcionalidade ou uma correção."
                  />
                  <form
                    className="request-form"
                    onSubmit={(event) => {
                      event.preventDefault()
                      submit.mutate()
                    }}
                  >
                    <label className="form-field">
                      Título da solicitação
                      <input
                        required
                        maxLength={160}
                        value={title}
                        onChange={(e) => {
                          setTitle(e.target.value)
                          submit.reset()
                        }}
                        placeholder="Criar API de recomendação de filmes"
                        disabled={
                          project.data.state === 'archived' || submit.isPending
                        }
                      />
                    </label>
                    <label className="form-field">
                      Requisitos em linguagem natural
                      <textarea
                        required
                        aria-label="Requisitos em linguagem natural"
                        aria-describedby="request-help"
                        maxLength={100000}
                        rows={10}
                        value={content}
                        onChange={(e) => {
                          setContent(e.target.value)
                          submit.reset()
                        }}
                        placeholder="Crie uma API FastAPI para um sistema de recomendação de filmes, com PostgreSQL, testes automatizados e documentação."
                        disabled={
                          project.data.state === 'archived' || submit.isPending
                        }
                      />
                      <small id="request-help">
                        Inclua o comportamento esperado, restrições e como
                        verificar o resultado.
                      </small>
                    </label>
                    {submit.error && (
                      <p className="form-error" role="alert">
                        {submit.error.message}
                      </p>
                    )}
                    {submit.isSuccess && (
                      <p className="text-green" role="status">
                        Solicitação salva no projeto.
                      </p>
                    )}
                    {project.data.state === 'archived' && (
                      <p className="text-amber">
                        Reative o projeto em “Editar projeto” para registrar
                        novas solicitações.
                      </p>
                    )}
                    <div className="form-actions">
                      <Button
                        variant="default"
                        type="submit"
                        disabled={
                          project.data.state === 'archived' || submit.isPending
                        }
                      >
                        <Plus size={15} />
                        {submit.isPending ? 'Salvando…' : 'Salvar solicitação'}
                      </Button>
                    </div>
                    <p className="form-footnote">
                      As solicitações ficam persistidas neste projeto. Use
                      “Iniciar execução” para confirmar os agentes e enviar os
                      requisitos ao worker.
                    </p>
                  </form>
                </section>
                <section className="panel">
                  <SectionTitle
                    title="Solicitações do projeto"
                    subtitle="Requisitos salvos para o próximo ciclo de desenvolvimento"
                  />
                  {requests.isError && (
                    <ErrorState
                      error={requests.error}
                      retry={requests.refetch}
                    />
                  )}
                  {requests.isPending ? (
                    <Loading />
                  ) : requests.data?.length ? (
                    <div className="project-request-list">
                      {requests.data.map((request) => (
                        <article
                          className="request-execution-card"
                          key={request.id}
                        >
                          <details className="project-request-item">
                            <summary>
                              <FileText size={17} />
                              <div>
                                <strong>{request.title}</strong>
                                <span>{date(request.created_at)}</span>
                              </div>
                              <span className="request-state">Registrada</span>
                            </summary>
                            <p className="preserve">{request.content}</p>
                          </details>
                          <div className="request-execution-actions">
                            <Button
                              disabled={project.data.state !== 'active'}
                              onClick={() => setSelectedRequest(request)}
                            >
                              <Play size={13} />
                              Iniciar execução
                            </Button>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    !requests.isError && (
                      <Empty title="Nenhuma solicitação ainda">
                        Registre o primeiro requisito usando o formulário ao
                        lado.
                      </Empty>
                    )
                  )}
                </section>
              </div>
            ) : (
              <ProjectHistory
                runs={runs.data}
                pending={runs.isPending}
                error={runs.error}
                retry={runs.refetch}
              />
            )}
            {selectedRequest && (
              <StartExecution
                project={project.data}
                task={selectedRequest}
                onClose={() => setSelectedRequest(null)}
              />
            )}
          </>
        )
      )}
    </>
  )
}

function ProjectEditor({
  project,
  onClose,
}: {
  project: Project
  onClose: () => void
}) {
  const [form, setForm] = useState({
    name: project.name,
    description: project.description,
    objectives: project.objectives,
    state: project.state,
  })
  const client = useQueryClient()
  const save = useMutation({
    mutationFn: () => mutate<Project>(`/projects/${project.id}`, form, 'PATCH'),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['projects'] }),
        client.invalidateQueries({ queryKey: ['project', project.id] }),
      ])
      onClose()
    },
  })
  return (
    <section className="panel project-editor">
      <SectionTitle
        title="Editar projeto"
        subtitle="A associação do repositório é preservada."
      />
      <form
        className="request-form"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate()
        }}
      >
        <label className="form-field">
          Nome do projeto
          <input
            required
            maxLength={120}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </label>
        <label className="form-field">
          Descrição
          <textarea
            maxLength={5000}
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </label>
        <label className="form-field">
          Objetivos
          <textarea
            maxLength={10000}
            value={form.objectives}
            onChange={(e) => setForm({ ...form, objectives: e.target.value })}
          />
        </label>
        <label className="form-field">
          Estado
          <select
            value={form.state}
            onChange={(e) =>
              setForm({ ...form, state: e.target.value as Project['state'] })
            }
          >
            <option value="active">Ativo</option>
            <option value="archived">Arquivado</option>
          </select>
        </label>
        {save.error && (
          <p role="alert" className="form-error">
            {save.error.message}
          </p>
        )}
        <div className="form-actions">
          <Button onClick={onClose} type="button" disabled={save.isPending}>
            Cancelar
          </Button>
          <Button variant="default" disabled={save.isPending} type="submit">
            {save.isPending ? 'Salvando…' : 'Salvar alterações'}
          </Button>
        </div>
      </form>
    </section>
  )
}
function ProjectHistory({
  runs,
  pending,
  error,
  retry,
}: {
  runs?: Run[]
  pending: boolean
  error: Error | null
  retry: () => unknown
}) {
  return (
    <section className="panel">
      <SectionTitle
        title="Execuções do repositório"
        subtitle="Execuções vinculadas às solicitações e histórico legado identificado pelo caminho do repositório."
      />
      {error && <ErrorState error={error} retry={retry} />}
      {pending ? (
        <Loading />
      ) : runs?.length ? (
        <div className="project-history">
          {runs.map((run) => (
            <Link
              key={run.run_id}
              to={`/executions/${encodeURIComponent(run.run_id)}`}
            >
              <GitBranch size={18} />
              <div>
                <strong>
                  {run.request_title ??
                    `Execução do CLI · ${date(run.started_at ?? run.last_event)}`}
                </strong>
                <span>
                  {run.project_id
                    ? 'Vinculada à solicitação'
                    : 'Histórico do repositório'}{' '}
                  · {run.task_count ?? '—'} tarefas · duração registrada:{' '}
                  {duration(run.duration_seconds)}
                </span>
              </div>
              <Status status={run.status} />
              <TestBadge passed={run.tests_passed} />
              <ArrowRight size={15} />
            </Link>
          ))}
        </div>
      ) : (
        !error && (
          <Empty title="Nenhuma execução deste repositório">
            Execuções do CLI com este mesmo caminho aparecerão aqui. Nenhuma
            execução foi iniciada pelo cadastro do projeto.
          </Empty>
        )
      )}
    </section>
  )
}
