import {
  Activity,
  ArrowRight,
  CheckCheck,
  Clock3,
  GitBranch,
  Hand,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react'
import { Link, useOutletContext } from 'react-router-dom'
import { useOverview, useRuns } from '../lib/api'
import {
  date,
  duration,
  eventSummary,
  parseEvent,
  stageLabels,
  statusLabels,
} from '../lib/events'
import {
  Empty,
  ErrorState,
  Loading,
  RunTable,
  SectionTitle,
} from '../components/shared'
import { Button } from '../components/ui/button'
import type { DashboardContext } from '../components/layout/Layout'
export function OverviewPage() {
  const { interval } = useOutletContext<DashboardContext>()
  const overview = useOverview(interval),
    runs = useRuns(new URLSearchParams({ limit: '6' }), interval)
  const data = overview.data
  const metrics = [
    {
      label: 'Total de execuções',
      value: data?.total,
      icon: GitBranch,
      color: 'neutral',
      hint: 'Todas as execuções registradas',
    },
    {
      label: 'Concluídas',
      value: data
        ? (data.counts.completed ?? 0) +
          (data.counts.success ?? 0) +
          (data.counts.succeeded ?? 0)
        : undefined,
      icon: CheckCheck,
      color: 'green',
      hint: 'Status final de conclusão',
    },
    {
      label: 'Em andamento',
      value: data?.counts.running ?? (data ? 0 : undefined),
      icon: Activity,
      color: 'blue',
      hint: 'Último estado registrado',
    },
    {
      label: 'Bloqueadas',
      value: data?.counts.blocked ?? (data ? 0 : undefined),
      icon: ShieldAlert,
      color: 'red',
      hint: 'Intervenção necessária',
    },
    {
      label: 'Revisão humana',
      value: data?.counts.ready_for_human_review ?? (data ? 0 : undefined),
      icon: Hand,
      color: 'amber',
      hint: 'Aguardando análise humana',
    },
    {
      label: 'Duração média',
      value: data ? duration(data.average_duration_seconds) : undefined,
      icon: Clock3,
      color: 'neutral',
      hint: data
        ? `${data.duration_sample_count} execuções com início e término`
        : 'Somente durações registradas',
    },
  ]
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">WORKSPACE OVERVIEW</div>
          <h1>
            Seu workflow, em perspectiva<span>.</span>
          </h1>
          <p>Acompanhe agentes, execuções e resultados em um só lugar.</p>
        </div>
        <Button
          onClick={() => {
            void overview.refetch()
            void runs.refetch()
          }}
        >
          <RefreshCw size={15} />
          Atualizar
        </Button>
      </div>
      {overview.isError && (
        <ErrorState error={overview.error} retry={overview.refetch} />
      )}
      <div className="metrics">
        {metrics.map(({ label, value, icon: Icon, color, hint }) => (
          <article className="metric" key={label}>
            <div className="metric-top">
              <span>{label}</span>
              <Icon className={`text-${color}`} size={17} />
            </div>
            <strong>{value ?? '—'}</strong>
            <small>{hint}</small>
          </article>
        ))}
      </div>
      <section className="panel">
        <SectionTitle
          title="Execuções recentes"
          subtitle="Última atividade dos workflows registrados"
          action={
            <Button asChild variant="ghost" size="sm">
              <Link to="/executions">
                Ver todas <ArrowRight size={14} />
              </Link>
            </Button>
          }
        />
        {runs.isError && <ErrorState error={runs.error} retry={runs.refetch} />}
        {runs.isPending ? (
          <Loading />
        ) : (
          runs.data && <RunTable runs={runs.data.items} />
        )}
      </section>
      <div className="overview-bottom">
        <section className="panel">
          <SectionTitle
            title="Distribuição de estados"
            subtitle="Todas as execuções do workspace"
          />
          {overview.isPending ? (
            <Loading />
          ) : data && data.total > 0 ? (
            <div className="distribution">
              <div className="distribution-total">
                <strong>{data.total}</strong>
                <span>execuções registradas</span>
              </div>
              <div className="distribution-track">
                {Object.entries(data.counts).map(([status, count]) => (
                  <div
                    className={`segment segment-${status}`}
                    style={{ flex: count }}
                    key={status}
                    title={`${statusLabels[status] ?? status}: ${count}`}
                  />
                ))}
              </div>
              <div className="distribution-legend">
                {Object.entries(data.counts).map(([status, count]) => (
                  <div key={status}>
                    <span>
                      <i className={`segment-${status}`} />
                      {statusLabels[status] ?? status}
                    </span>
                    <strong>
                      {count}
                      <small>{Math.round((count / data.total) * 100)}%</small>
                    </strong>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <Empty title="Sem estados registrados" />
          )}
        </section>
        <section className="panel">
          <SectionTitle
            title="Atividade recente"
            subtitle="Eventos registrados pelo orquestrador"
          />
          {overview.isPending ? (
            <Loading />
          ) : data?.activity.length ? (
            <div className="activity-list">
              {data.activity.map((e, i) => (
                <Link
                  key={e.id ?? i}
                  to={`/executions/${encodeURIComponent(e.run_id)}`}
                  className="activity-item"
                >
                  <span className={`activity-dot dot-${e.stage}`} />
                  <div>
                    <strong>{stageLabels[e.stage] ?? e.stage}</strong>
                    <p>{eventSummary(parseEvent(e))}</p>
                    <small className="mono">{e.run_id}</small>
                  </div>
                  <time>{date(e.at)}</time>
                </Link>
              ))}
            </div>
          ) : (
            <Empty title="Nenhuma atividade registrada" />
          )}
        </section>
      </div>
      <div className="info-note">
        <Activity size={14} />O estado reflete o último evento registrado.
        Execuções sem término não possuem confirmação de atividade ou duração
        final.
      </div>
    </>
  )
}
