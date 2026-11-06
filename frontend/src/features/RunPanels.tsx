import {
  Bot,
  CheckCircle2,
  Code2,
  FileText,
  GitPullRequest,
  Layers,
  ShieldCheck,
} from 'lucide-react'
import type { ParsedEvent, RunDetail } from '../types'
import {
  eventSummary,
  list,
  object,
  text,
  reviewPayload,
  plannedTasks,
} from '../lib/events'
import { Empty, RawData, SectionTitle, TestBadge } from '../components/shared'
export function TaskPlan({ events }: { events: ParsedEvent[] }) {
  const planned = events.filter((e) => e.stage === 'plan').at(-1)
  const tasks = plannedTasks(planned?.data ?? {})
  return (
    <section className="panel">
      <SectionTitle
        title="Plano de trabalho"
        subtitle={`${tasks.length || 'Nenhuma'} tarefas registradas`}
      />
      {tasks.length ? (
        <div className="task-list">
          {tasks.map((raw, i) => {
            const task = object(raw)
            return (
              <details className="task-item" key={i}>
                <summary>
                  <span className="task-id">{text(task.id, `#${i + 1}`)}</span>
                  <strong>{text(task.title, 'Tarefa sem título')}</strong>
                  <span className="muted">Detalhes</span>
                </summary>
                <div className="task-body">
                  <p className="preserve">{text(task.instructions)}</p>
                  <h4>Critérios de aceitação</h4>
                  <StringList values={task.acceptance} />
                  <h4>Testes planejados</h4>
                  <StringList values={task.tests} />
                </div>
              </details>
            )
          })}
        </div>
      ) : (
        <Empty title="Plano ainda não registrado" />
      )}
    </section>
  )
}
export function StringList({ values }: { values: unknown }) {
  const items = list(values)
  return items.length ? (
    <ul className="findings">
      {items.map((v, i) => (
        <li key={i}>{typeof v === 'string' ? v : JSON.stringify(v)}</li>
      ))}
    </ul>
  ) : (
    <p className="muted">Nenhum item registrado.</p>
  )
}
export function ReviewContent({ event }: { event: ParsedEvent }) {
  const p = reviewPayload(event.data),
    result = p.test_result
  return (
    <div className="review-content">
      <div className="review-verdict">
        <ShieldCheck size={18} />
        <strong>
          {p.approved === true
            ? 'Revisão automática aprovada'
            : p.approved === false
              ? 'Revisão automática reprovada'
              : 'Resultado da revisão desconhecido'}
        </strong>
        <span className="muted">{text(p.task, 'Tarefa não registrada')}</span>
      </div>
      <div className="test-result">
        <span>Testes automatizados</span>
        <TestBadge passed={result.passed} />
      </div>
      <h4>Findings</h4>
      <StringList values={p.findings} />
      <h4>Recomendações de testes</h4>
      <StringList values={p.test_suggestions} />
      {(typeof result.output === 'string' ||
        typeof result.error === 'string') && (
        <details className="test-output">
          <summary>Saída completa registrada dos testes</summary>
          <pre>
            {text(result.output, '')}
            {typeof result.error === 'string' ? `\n${result.error}` : ''}
          </pre>
          <small>
            O orquestrador pode truncar a saída antes de gravá-la no banco.
          </small>
        </details>
      )}
    </div>
  )
}
export function EventContent({ event }: { event: ParsedEvent }) {
  const p = event.data
  return (
    <div className="event-content">
      {event.malformed ? (
        <p className="text-amber">
          Não foi possível interpretar este payload. O conteúdo original está
          disponível abaixo.
        </p>
      ) : (
        <>
          {event.stage === 'review' ? (
            <ReviewContent event={event} />
          ) : event.stage === 'implementation' ? (
            <>
              <div className="inline-meta">
                <span>Tarefa: {text(p.task)}</span>
                <span>Tentativa: {text(p.attempt)}</span>
              </div>
              <pre className="console">
                {text(p.output, 'Sem resumo registrado.')}
              </pre>
            </>
          ) : event.stage === 'plan' ? (
            <div className="event-tasks">
              {list(p.tasks).map((task, i) => (
                <div key={i}>
                  <strong>
                    {text(object(task).id)} · {text(object(task).title)}
                  </strong>
                  <p className="preserve">{text(object(task).instructions)}</p>
                </div>
              ))}
            </div>
          ) : (
            <>
              <p className="preserve">{eventSummary(event)}</p>
              <dl className="metadata compact">
                {Object.entries(p)
                  .filter(
                    ([key, value]) =>
                      key !== 'message' &&
                      (typeof value === 'string' || typeof value === 'number'),
                  )
                  .map(([key, value]) => (
                    <div key={key}>
                      <dt>{key}</dt>
                      <dd>{text(value)}</dd>
                    </div>
                  ))}
              </dl>
            </>
          )}
        </>
      )}
      <RawData value={event.raw} />
    </div>
  )
}
export function AgentPanels({
  run,
  events,
}: {
  run: RunDetail
  events: ParsedEvent[]
}) {
  const stages = [
    {
      role: 'Planner',
      stage: 'plan',
      icon: FileText,
      description: 'Decomposição e planejamento',
    },
    {
      role: 'Implementer',
      stage: 'implementation',
      icon: Code2,
      description: 'Implementação das tarefas',
    },
    {
      role: 'Reviewer',
      stage: 'review',
      icon: GitPullRequest,
      description: 'Revisão independente e QA',
    },
  ]
  return (
    <div className="agent-grid">
      {stages.map(({ role, stage, icon: Icon, description }) => {
        const related = events.filter((e) => e.stage === stage),
          last = related.at(-1),
          p = last?.data ?? {}
        const current =
          run.manager_status === 'running' && run.current_stage === stage
        const active = current && run.supervisor_online !== false
        return (
          <section className="panel agent-card" key={role}>
            <div className="agent-heading">
              <div className="agent-icon">
                <Icon size={22} />
              </div>
              <span
                className={active ? 'text-blue' : last ? 'text-green' : 'muted'}
              >
                <span className="tiny-dot" />
                {active
                  ? 'Em execução'
                  : current
                    ? 'Atividade não confirmada'
                    : last
                      ? 'Etapa registrada'
                      : 'Sem evento'}
              </span>
            </div>
            <h2>{role}</h2>
            <p className="muted">{description}</p>
            <dl className="agent-meta">
              <div>
                <dt>Provider histórico</dt>
                <dd>{text(p.provider)}</dd>
              </div>
              <div>
                <dt>Modelo</dt>
                <dd>{text(p.model)}</dd>
              </div>
              <div>
                <dt>Eventos relacionados</dt>
                <dd>{related.length}</dd>
              </div>
              {stage === 'plan' ? (
                <div>
                  <dt>Tarefas planejadas</dt>
                  <dd>{run.task_count ?? 'Não registrado'}</dd>
                </div>
              ) : (
                <div>
                  <dt>Última tarefa</dt>
                  <dd>{text(p.task ?? p.task_id)}</dd>
                </div>
              )}
              {stage === 'implementation' && (
                <>
                  <div>
                    <dt>Chamadas registradas</dt>
                    <dd>{run.attempts}</dd>
                  </div>
                  <div>
                    <dt>Última tentativa</dt>
                    <dd>{text(p.attempt)}</dd>
                  </div>
                </>
              )}
            </dl>
            {last && (
              <div className="agent-result">
                {stage === 'review' ? (
                  <ReviewContent event={last} />
                ) : (
                  <>
                    <h4>
                      {stage === 'plan'
                        ? 'Último planejamento'
                        : 'Resumo da implementação'}
                    </h4>
                    <p className="preserve">
                      {stage === 'plan'
                        ? eventSummary(last)
                        : text(p.output, 'Resumo não registrado')}
                    </p>
                  </>
                )}
              </div>
            )}
          </section>
        )
      })}
    </div>
  )
}
export function ReviewsPanel({ events }: { events: ParsedEvent[] }) {
  const reviews = events.filter((e) => e.stage === 'review')
  return (
    <section className="panel">
      <SectionTitle
        title="Testes e revisões"
        subtitle={`${reviews.length} revisões · ${events.filter((e) => e.stage === 'implementation').length} implementações registradas`}
      />
      {reviews.length ? (
        <div className="reviews-list">
          {reviews.map((e, i) => (
            <details
              className="review-item"
              key={e.id ?? i}
              open={i === reviews.length - 1}
            >
              <summary>
                <CheckCircle2 size={16} />
                <strong>{text(e.data.task, 'Tarefa desconhecida')}</strong>
                <span>Revisão #{i + 1}</span>
                <TestBadge passed={object(e.data.test_result).passed} />
              </summary>
              <ReviewContent event={e} />
              <RawData value={e.raw} />
            </details>
          ))}
        </div>
      ) : (
        <Empty title="Nenhuma revisão registrada">
          Os resultados serão exibidos após o QA registrar um evento.
        </Empty>
      )}
    </section>
  )
}
export function RunFacts({ run }: { run: RunDetail }) {
  return (
    <div className="detail-callouts">
      <span>
        <Layers size={16} />
        {run.task_count ?? '—'} tarefas planejadas
      </span>
      <span>
        <Code2 size={16} />
        {run.attempts} implementações registradas
      </span>
      <span>
        <Bot size={16} />
        Providers históricos apenas quando registrados
      </span>
    </div>
  )
}
