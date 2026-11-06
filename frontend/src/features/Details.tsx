import {
  ArrowLeft,
  ChevronDown,
  Clock3,
  FolderGit2,
  GitBranch,
  RefreshCw,
} from 'lucide-react'
import {
  Link,
  useOutletContext,
  useParams,
  useSearchParams,
} from 'react-router-dom'
import { useRun } from '../lib/api'
import {
  date,
  duration,
  eventSummary,
  parseEvent,
  stageLabels,
} from '../lib/events'
import {
  Empty,
  ErrorState,
  Loading,
  SectionTitle,
  Status,
} from '../components/shared'
import { Button } from '../components/ui/button'
import {
  AgentPanels,
  EventContent,
  ReviewsPanel,
  RunFacts,
  TaskPlan,
} from './RunPanels'
import type { DashboardContext } from '../components/layout/Layout'
export function DetailsPage() {
  const { runId = '' } = useParams(),
    { interval } = useOutletContext<DashboardContext>()
  const query = useRun(runId, interval)
  const [params, setParams] = useSearchParams()
  const tab = ['timeline', 'tasks', 'agents', 'reviews'].includes(
    params.get('tab') ?? '',
  )
    ? params.get('tab')!
    : 'timeline'
  const run = query.data,
    events = run?.events.map(parseEvent) ?? []
  return (
    <>
      <Link
        className="back-link"
        to={run?.project_id ? `/projects/${run.project_id}` : '/executions'}
      >
        <ArrowLeft size={14} />
        {run?.project_name ?? 'Todas as execuções'}
      </Link>
      <div className="page-heading">
        <div>
          <div className="eyebrow">EXECUTION DETAILS</div>
          <h1 className={run?.request_title ? undefined : 'mono run-title'}>
            {run?.request_title ?? runId}
          </h1>
          <p>
            {run?.project_name
              ? `${run.project_name} · acompanhamento da execução`
              : 'O histórico completo de cada etapa do workflow.'}
          </p>
        </div>
        <Button onClick={() => void query.refetch()}>
          <RefreshCw size={15} />
          Atualizar
        </Button>
      </div>
      {query.isError && (
        <ErrorState error={query.error} retry={query.refetch} />
      )}
      {query.isPending ? (
        <Loading />
      ) : (
        run && (
          <>
            {run.manager_status === 'queued' && (
              <div className="info-note">
                Solicitação persistida na fila. O worker iniciará o workflow
                quando concluir o despacho anterior.
              </div>
            )}
            {run.supervisor_online === false && (
              <p role="alert" className="form-error">
                Worker sem confirmação de atividade. O estado persistido pode
                estar desatualizado; reinicie o worker para reconciliar a
                execução. Nenhuma chamada de agente será repetida
                automaticamente.
              </p>
            )}
            {run.error && (
              <p role="alert" className="form-error">
                {run.error}
              </p>
            )}
            {run.orphaned && (
              <p role="alert" className="form-error">
                Repositório reservado: existe um processo órfão que precisa ser
                inspecionado antes de outra execução.
              </p>
            )}
            <section className="panel execution-summary">
              <div className="execution-summary-top">
                <div>
                  <GitBranch size={20} />
                  <strong>{run.run_id}</strong>
                </div>
                <Status status={run.status} />
              </div>
              <dl className="metadata">
                <div>
                  <dt>
                    <FolderGit2 size={13} />
                    Repositório
                  </dt>
                  <dd>{run.repo ?? 'Não registrado'}</dd>
                </div>
                <div>
                  <dt>Worktree</dt>
                  <dd>{run.worktree ?? 'Não registrada'}</dd>
                </div>
                <div>
                  <dt>Início</dt>
                  <dd>{date(run.started_at)}</dd>
                </div>
                <div>
                  <dt>Término registrado</dt>
                  <dd>{date(run.finished_at)}</dd>
                </div>
                <div>
                  <dt>
                    <Clock3 size={13} />
                    Duração registrada
                  </dt>
                  <dd>{duration(run.duration_seconds)}</dd>
                </div>
                <div>
                  <dt>Última etapa</dt>
                  <dd>
                    {stageLabels[run.current_stage ?? ''] ??
                      run.current_stage ??
                      'Desconhecida'}
                  </dd>
                </div>
              </dl>
              <RunFacts run={run} />
              {run.configuration && (
                <details className="test-output">
                  <summary>Configuração usada nesta execução</summary>
                  <dl className="metadata compact">
                    <div>
                      <dt>Planner configurado</dt>
                      <dd>
                        {run.configuration.planner} ·{' '}
                        {run.configuration.planner_model ??
                          'modelo padrão do CLI'}
                      </dd>
                    </div>
                    <div>
                      <dt>Implementer configurado</dt>
                      <dd>
                        {run.configuration.implementer} ·{' '}
                        {run.configuration.implementer_model ??
                          'modelo padrão do CLI'}
                      </dd>
                    </div>
                    <div>
                      <dt>Reviewer</dt>
                      <dd>Codex · modelo padrão do CLI</dd>
                    </div>
                    <div>
                      <dt>Comando de testes</dt>
                      <dd className="mono">{run.configuration.test_command}</dd>
                    </div>
                  </dl>
                </details>
              )}
            </section>
            <div
              className="tabs"
              role="tablist"
              aria-label="Detalhes da execução"
              onKeyDown={(event) => {
                const keys = ['timeline', 'tasks', 'agents', 'reviews']
                const index = keys.indexOf(tab)
                const next =
                  event.key === 'ArrowRight'
                    ? keys[(index + 1) % keys.length]
                    : event.key === 'ArrowLeft'
                      ? keys[(index + keys.length - 1) % keys.length]
                      : event.key === 'Home'
                        ? keys[0]
                        : event.key === 'End'
                          ? keys.at(-1)
                          : undefined
                if (next) {
                  event.preventDefault()
                  setParams({ tab: next }, { replace: true })
                  document.getElementById(`tab-${next}`)?.focus()
                }
              }}
            >
              {[
                ['timeline', 'Timeline'],
                ['tasks', 'Tarefas'],
                ['agents', 'Agentes'],
                ['reviews', 'Testes e revisões'],
              ].map(([key, label]) => (
                <Button
                  role="tab"
                  tabIndex={tab === key ? 0 : -1}
                  aria-selected={tab === key}
                  aria-controls={`panel-${key}`}
                  id={`tab-${key}`}
                  variant="ghost"
                  key={key}
                  onClick={() => setParams({ tab: key }, { replace: true })}
                >
                  {label}
                  {key === 'timeline' && (
                    <span className="count">{events.length}</span>
                  )}
                </Button>
              ))}
            </div>
            <div
              role="tabpanel"
              id={`panel-${tab}`}
              aria-labelledby={`tab-${tab}`}
            >
              {tab === 'timeline' ? (
                <section className="panel">
                  <SectionTitle
                    title="Timeline de eventos"
                    subtitle="Ordem de gravação no SQLite · inclui tentativas e retomadas"
                  />
                  {events.length ? (
                    <div className="timeline">
                      {events.map((event, i) => (
                        <details
                          className={`timeline-event timeline-${event.stage}`}
                          key={event.id ?? i}
                        >
                          <summary>
                            <span className="timeline-node">
                              {String(i + 1).padStart(2, '0')}
                            </span>
                            <div>
                              <strong>
                                {stageLabels[event.stage] ?? event.stage}
                              </strong>
                              <p>{eventSummary(event)}</p>
                            </div>
                            <time>{date(event.at)}</time>
                            <ChevronDown size={15} />
                          </summary>
                          <EventContent event={event} />
                        </details>
                      ))}
                    </div>
                  ) : (
                    <Empty title="Sem eventos registrados" />
                  )}
                </section>
              ) : tab === 'tasks' ? (
                <TaskPlan events={events} />
              ) : tab === 'agents' ? (
                <AgentPanels run={run} events={events} />
              ) : (
                <ReviewsPanel events={events} />
              )}
            </div>
            {run.status === 'ready_for_human_review' && (
              <div className="info-note text-amber">
                O workflow terminou e aguarda revisão humana. A aprovação
                automática do reviewer não representa aprovação humana. O
                dashboard não realiza merge, push ou deploy.
              </div>
            )}
          </>
        )
      )}
    </>
  )
}
