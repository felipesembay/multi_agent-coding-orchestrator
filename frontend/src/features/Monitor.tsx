import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react'
import { Link, useOutletContext, useSearchParams } from 'react-router-dom'
import { useRun, useRuns } from '../lib/api'
import { parseEvent } from '../lib/events'
import { Empty, ErrorState, Loading, Status } from '../components/shared'
import { Button } from '../components/ui/button'
import { AgentPanels, ReviewsPanel } from './RunPanels'
import type { DashboardContext } from '../components/layout/Layout'
export function MonitorPage({ reviews = false }: { reviews?: boolean }) {
  const { interval } = useOutletContext<DashboardContext>()
  const [params, setParams] = useSearchParams()
  const offset = Math.max(0, Number(params.get('offset')) || 0)
  const runs = useRuns(
    new URLSearchParams({ limit: '20', offset: String(offset) }),
    interval,
  )
  const selected = params.get('run') ?? runs.data?.items[0]?.run_id ?? ''
  const run = useRun(selected, interval)
  const page = (value: number) => {
    const next = new URLSearchParams(params)
    next.set('offset', String(value))
    setParams(next, { replace: true })
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            {reviews ? 'QUALITY & VALIDATION' : 'WORKFLOW PARTICIPANTS'}
          </div>
          <h1>
            {reviews ? 'Tests & Reviews' : 'Agent Monitor'}
            <span>.</span>
          </h1>
          <p>
            {reviews
              ? 'Evidências dos testes e das revisões automáticas, por execução.'
              : 'Planejamento, implementação e revisão com evidência por etapa.'}
          </p>
        </div>
        <Button
          onClick={() => {
            void runs.refetch()
            if (selected) void run.refetch()
          }}
        >
          <RefreshCw size={15} />
          Atualizar
        </Button>
      </div>
      {runs.isError && <ErrorState error={runs.error} retry={runs.refetch} />}
      {runs.isPending ? (
        <Loading />
      ) : (
        runs.data && (
          <div className="run-selector">
            <label>
              Execução
              <select
                aria-label="Selecionar execução"
                value={selected}
                onChange={(e) => {
                  const next = new URLSearchParams(params)
                  next.set('run', e.target.value)
                  setParams(next)
                }}
              >
                {selected &&
                  !runs.data.items.some((r) => r.run_id === selected) && (
                    <option value={selected}>{selected}</option>
                  )}
                {runs.data.items.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.run_id} · {r.repo?.split('/').pop() ?? 'Sem repositório'}
                  </option>
                ))}
              </select>
            </label>
            <Button
              size="icon"
              aria-label="Execuções anteriores"
              disabled={!offset}
              onClick={() => page(Math.max(0, offset - 20))}
            >
              <ChevronLeft size={15} />
            </Button>
            <Button
              size="icon"
              aria-label="Mais execuções"
              disabled={offset + 20 >= runs.data.total}
              onClick={() => page(offset + 20)}
            >
              <ChevronRight size={15} />
            </Button>
            {run.data && (
              <>
                <Status status={run.data.status} />
                <Link
                  className="inline-link"
                  to={`/executions/${encodeURIComponent(selected)}`}
                >
                  Abrir detalhes →
                </Link>
              </>
            )}
          </div>
        )
      )}
      {!selected && !runs.isPending && !runs.isError ? (
        <Empty />
      ) : (
        selected && (
          <>
            {run.isError && (
              <ErrorState error={run.error} retry={run.refetch} />
            )}
            {run.isPending ? (
              <Loading />
            ) : (
              run.data &&
              (reviews ? (
                <ReviewsPanel events={run.data.events.map(parseEvent)} />
              ) : (
                <AgentPanels
                  run={run.data}
                  events={run.data.events.map(parseEvent)}
                />
              ))
            )}
          </>
        )
      )}
      <div className="info-note">
        {reviews
          ? 'Resultados de QA são automáticos. A análise e aprovação humanas continuam sendo uma etapa separada.'
          : 'Providers e modelos históricos só são exibidos quando presentes nos eventos. A configuração atual do servidor está em Settings.'}
      </div>
    </>
  )
}
