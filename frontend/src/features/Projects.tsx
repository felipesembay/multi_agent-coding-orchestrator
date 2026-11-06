import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  FolderGit2,
  FolderPlus,
  GitBranch,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
} from 'lucide-react'
import { Link, useNavigate, useOutletContext } from 'react-router-dom'
import { Button } from '../components/ui/button'
import { Empty, ErrorState, Loading } from '../components/shared'
import { date } from '../lib/events'
import { mutate, useProjectPolicy, useProjects } from '../lib/projects'
import type { DashboardContext } from '../components/layout/Layout'
import type { Project, ProjectInput, ProjectPreview } from '../types'

export function ProjectsPage() {
  const { interval } = useOutletContext<DashboardContext>()
  const projects = useProjects(interval)
  const [search, setSearch] = useState('')
  const [state, setState] = useState('active')
  const filtered = projects.data?.filter(
    (p) =>
      (state === 'all' || p.state === state) &&
      `${p.name} ${p.description}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()),
  )
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">PROJECT WORKSPACE</div>
          <h1>
            Seus projetos<span>.</span>
          </h1>
          <p>
            Organize objetivos, repositórios e solicitações de desenvolvimento.
          </p>
        </div>
        <div className="heading-actions">
          <Button
            aria-label="Atualizar projetos"
            onClick={() => void projects.refetch()}
          >
            <RefreshCw size={15} />
          </Button>
          <Button variant="default" asChild>
            <Link to="/projects/new">
              <Plus size={16} />
              Novo projeto
            </Link>
          </Button>
        </div>
      </div>
      <div className="project-intro">
        <span className="project-intro-icon">
          <FolderGit2 size={25} />
        </span>
        <div>
          <h2>Do objetivo ao workspace</h2>
          <p>
            Crie um projeto ou conecte um repositório existente. Descreva o que
            deseja desenvolver e mantenha as solicitações salvas no mesmo lugar.
          </p>
        </div>
        <span className="phase-label">Projetos e solicitações</span>
      </div>
      <div className="project-toolbar">
        <label className="search">
          <Search size={16} />
          <input
            aria-label="Buscar projetos"
            placeholder="Buscar por nome ou descrição…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <select
          aria-label="Estado dos projetos"
          value={state}
          onChange={(e) => setState(e.target.value)}
        >
          <option value="active">Projetos ativos</option>
          <option value="archived">Arquivados</option>
          <option value="all">Todos os projetos</option>
        </select>
        <span className="muted">{filtered?.length ?? '—'} projetos</span>
      </div>
      {projects.isError && (
        <ErrorState error={projects.error} retry={projects.refetch} />
      )}
      {projects.isPending ? (
        <Loading />
      ) : (
        filtered &&
        (filtered.length ? (
          <div className="project-grid">
            {filtered.map((project) => (
              <Link
                className="project-card"
                key={project.id}
                to={`/projects/${project.id}`}
              >
                <div className="project-card-top">
                  <span className="project-avatar">
                    <FolderGit2 size={22} />
                  </span>
                  <span className={`project-state ${project.state}`}>
                    {project.state === 'active' ? 'Ativo' : 'Arquivado'}
                  </span>
                </div>
                <h2>{project.name}</h2>
                <p>
                  {project.description ||
                    'Adicione uma descrição para contextualizar este projeto.'}
                </p>
                <div className="project-repo">
                  <GitBranch size={13} />
                  <span title={project.repo_path}>{project.repo_path}</span>
                </div>
                <div className="project-card-bottom">
                  <span>{project.request_count ?? 0} solicitações</span>
                  <span>Atualizado em {date(project.updated_at)}</span>
                  <ArrowRight size={15} />
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <section className="panel">
            <Empty
              title={
                search || state !== 'active'
                  ? 'Nenhum projeto com esses filtros'
                  : 'Seu próximo projeto começa aqui'
              }
            >
              {search || state !== 'active'
                ? 'Ajuste a busca ou o estado para encontrar um projeto.'
                : 'Cadastre um repositório ou crie um projeto novo para começar a registrar seus requisitos.'}
            </Empty>
            {!search && state === 'active' && (
              <div className="empty-action">
                <Button variant="default" asChild>
                  <Link to="/projects/new">
                    <FolderPlus size={16} />
                    Criar primeiro projeto
                  </Link>
                </Button>
              </div>
            )}
          </section>
        ))
      )}
    </>
  )
}

export function NewProjectPage() {
  const policy = useProjectPolicy()
  const navigate = useNavigate(),
    client = useQueryClient()
  const [form, setForm] = useState<ProjectInput>({
    name: '',
    description: '',
    objectives: '',
    repo_path: '',
    mode: 'existing',
  })
  const [preview, setPreview] = useState<ProjectPreview | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const review = useMutation({
    mutationFn: (data: ProjectInput) =>
      mutate<ProjectPreview>('/projects/preview', data),
    onSuccess: (value) => {
      setPreview(value)
      setConfirmed(false)
    },
  })
  const create = useMutation({
    mutationFn: () =>
      mutate<Project>('/projects', {
        preview_token: preview?.preview_token,
        confirmed,
      }),
    onSuccess: async (project) => {
      await client.invalidateQueries({ queryKey: ['projects'] })
      navigate(`/projects/${project.id}`)
    },
  })
  const update = (key: keyof ProjectInput, value: string) => {
    setForm((previous) => ({ ...previous, [key]: value }))
    review.reset()
  }
  const unavailable =
    !policy.data?.roots.some((root) => root.available) ||
    !policy.data.git_available
  return (
    <>
      <Link to="/" className="back-link">
        <ArrowLeft size={14} />
        Todos os projetos
      </Link>
      <div className="page-heading">
        <div>
          <div className="eyebrow">NEW PROJECT</div>
          <h1>
            Um espaço para construir<span>.</span>
          </h1>
          <p>Dê um nome ao projeto e escolha onde seu código será mantido.</p>
        </div>
      </div>
      {policy.isError && (
        <ErrorState error={policy.error} retry={policy.refetch} />
      )}
      {policy.isPending ? (
        <Loading />
      ) : (
        policy.data && (
          <div className="project-form-grid">
            <section className="panel project-form-panel">
              {preview ? (
                <div className="project-confirmation" aria-live="polite">
                  <div className="confirmation-icon">
                    <ShieldCheck size={26} />
                  </div>
                  <h2>Revise antes de confirmar</h2>
                  <p>
                    Estas são as operações reais que serão realizadas no seu
                    computador.
                  </p>
                  <dl className="settings-list">
                    <div>
                      <dt>Projeto</dt>
                      <dd>{preview.project.name}</dd>
                    </div>
                    <div>
                      <dt>Repositório</dt>
                      <dd className="mono">{preview.project.repo_path}</dd>
                    </div>
                    <div>
                      <dt>Descrição</dt>
                      <dd className="preserve">
                        {preview.project.description || 'Não informada'}
                      </dd>
                    </div>
                    <div>
                      <dt>Objetivos</dt>
                      <dd className="preserve">
                        {preview.project.objectives || 'Não informados'}
                      </dd>
                    </div>
                  </dl>
                  <ul className="confirmation-actions">
                    {preview.actions.map((action) => (
                      <li key={action}>
                        <Check size={15} />
                        {action}
                      </li>
                    ))}
                  </ul>
                  <label className="confirmation-checkbox">
                    <input
                      type="checkbox"
                      checked={confirmed}
                      onChange={(e) => setConfirmed(e.target.checked)}
                    />
                    <span>
                      {preview.project.mode === 'create'
                        ? 'Autorizo criar este diretório, inicializar o Git e criar o commit inicial local.'
                        : 'Confirmo a associação deste repositório ao projeto.'}
                    </span>
                  </label>
                  {create.error && (
                    <p role="alert" className="form-error">
                      {create.error.message}
                    </p>
                  )}
                  <div className="form-actions">
                    <Button
                      disabled={create.isPending}
                      onClick={() => {
                        setPreview(null)
                        create.reset()
                        review.reset()
                      }}
                    >
                      Voltar e editar
                    </Button>
                    <Button
                      variant="default"
                      disabled={!confirmed || create.isPending}
                      onClick={() => create.mutate()}
                    >
                      {create.isPending
                        ? 'Salvando…'
                        : 'Confirmar e criar projeto'}
                    </Button>
                  </div>
                </div>
              ) : (
                <form
                  onSubmit={(event) => {
                    event.preventDefault()
                    review.mutate(form)
                  }}
                >
                  <fieldset
                    className="project-fields"
                    disabled={review.isPending}
                  >
                    <fieldset className="mode-options">
                      <legend>Como deseja começar?</legend>
                      <label
                        className={form.mode === 'existing' ? 'selected' : ''}
                      >
                        <input
                          type="radio"
                          name="mode"
                          value="existing"
                          checked={form.mode === 'existing'}
                          onChange={() => update('mode', 'existing')}
                        />
                        <GitBranch size={19} />
                        <strong>Repositório existente</strong>
                        <span>Conecte um projeto Git local.</span>
                      </label>
                      <label
                        className={form.mode === 'create' ? 'selected' : ''}
                      >
                        <input
                          type="radio"
                          name="mode"
                          value="create"
                          checked={form.mode === 'create'}
                          onChange={() => update('mode', 'create')}
                        />
                        <FolderPlus size={19} />
                        <strong>Criar projeto novo</strong>
                        <span>Inicialize um diretório e Git.</span>
                      </label>
                    </fieldset>
                    <label className="form-field">
                      Nome do projeto
                      <input
                        required
                        autoFocus
                        maxLength={120}
                        value={form.name}
                        onChange={(e) => update('name', e.target.value)}
                        placeholder="Sistema de Recomendação de Filmes"
                      />
                    </label>
                    <label className="form-field">
                      Descrição
                      <textarea
                        maxLength={5000}
                        rows={3}
                        value={form.description}
                        onChange={(e) => update('description', e.target.value)}
                        placeholder="Qual problema este projeto resolve?"
                      />
                    </label>
                    <label className="form-field">
                      Objetivos
                      <textarea
                        maxLength={10000}
                        rows={4}
                        value={form.objectives}
                        onChange={(e) => update('objectives', e.target.value)}
                        placeholder="Descreva os resultados que deseja alcançar."
                      />
                    </label>
                    <label className="form-field">
                      Caminho absoluto do repositório
                      <input
                        required
                        maxLength={4096}
                        value={form.repo_path}
                        onChange={(e) => update('repo_path', e.target.value)}
                        placeholder={
                          policy.data.roots[0]
                            ? `${policy.data.roots[0].path}/recomendacao-filmes`
                            : '/caminho/autorizado/recomendacao-filmes'
                        }
                      />
                      <small>
                        {form.mode === 'create'
                          ? 'O diretório final não pode existir; o diretório pai precisa existir.'
                          : 'Informe a raiz exata do repositório Git, sem links simbólicos.'}
                      </small>
                    </label>
                    {review.error && (
                      <p role="alert" className="form-error">
                        {review.error.message}
                      </p>
                    )}
                    <div className="form-actions">
                      <Button asChild>
                        <Link to="/">Cancelar</Link>
                      </Button>
                      <Button
                        type="submit"
                        variant="default"
                        disabled={unavailable || review.isPending}
                      >
                        {review.isPending ? 'Validando…' : 'Revisar projeto'}
                        <ArrowRight size={14} />
                      </Button>
                    </div>
                  </fieldset>
                </form>
              )}
            </section>
            <aside className="panel project-policy">
              <ShieldCheck size={24} />
              <h2>Diretórios autorizados</h2>
              <p>
                O backend só cadastra ou cria projetos dentro destas pastas.
              </p>
              {policy.data.roots.length ? (
                <ul>
                  {policy.data.roots.map((root) => (
                    <li key={root.path}>
                      <code>{root.path}</code>
                      <span
                        className={root.available ? 'text-green' : 'text-amber'}
                      >
                        {root.available
                          ? 'Disponível'
                          : 'Crie esta pasta no servidor'}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="setup-required">
                  <strong>Configure o acesso local</strong>
                  <p>
                    Defina uma pasta de projetos ao iniciar a API. Exemplo para
                    uma pasta que você autoriza:
                  </p>
                  <pre>
                    {
                      'mkdir -p "$HOME/projects"\nORCH_ALLOWED_ROOTS="$HOME/projects" \\\n  .venv/bin/python -m uvicorn orchestrator.api:app \\\n  --host 127.0.0.1 --port 8765'
                    }
                  </pre>
                  <p>Reinicie a API e atualize esta página após configurar.</p>
                </div>
              )}
              {!policy.data.git_available && (
                <p role="alert" className="form-error">
                  Git não encontrado no servidor. Instale-o antes de cadastrar
                  projetos.
                </p>
              )}
              <div className="info-note">
                Um projeto novo terá README e commit inicial local. Repositórios
                existentes serão apenas associados. Nenhum agente é executado
                nesta etapa.
              </div>
            </aside>
          </div>
        )
      )}
    </>
  )
}
