import {
  ArrowDownWideNarrow,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Search,
} from 'lucide-react'
import { useOutletContext, useSearchParams } from 'react-router-dom'
import { useRuns } from '../lib/api'
import { ErrorState, Loading, RunTable } from '../components/shared'
import { Button } from '../components/ui/button'
import { statusLabels } from '../lib/events'
import type { DashboardContext } from '../components/layout/Layout'
export function ExecutionsPage() {
  const { interval } = useOutletContext<DashboardContext>()
  const [params, setParams] = useSearchParams()
  const offset = Math.max(0, Number(params.get('offset')) || 0)
  const apiParams = new URLSearchParams({
    limit: '15',
    offset: String(offset),
    search: params.get('search') ?? '',
    status: params.get('status') ?? '',
    order: params.get('order') === 'asc' ? 'asc' : 'desc',
  })
  const runs = useRuns(apiParams, interval)
  const update = (key: string, value: string) =>
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        if (value) next.set(key, value)
        else next.delete(key)
        if (key !== 'offset') next.delete('offset')
        return next
      },
      { replace: true },
    )
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">WORKFLOW HISTORY</div>
          <h1>
            Executions<span>.</span>
          </h1>
          <p>Inspecione o histórico, do primeiro plano à revisão final.</p>
        </div>
        <Button onClick={() => void runs.refetch()}>
          <RefreshCw size={15} />
          Atualizar
        </Button>
      </div>
      <section className="panel">
        <div className="filters">
          <label className="search">
            <Search size={16} />
            <input
              aria-label="Buscar por Run ID"
              placeholder="Buscar por Run ID…"
              value={params.get('search') ?? ''}
              onChange={(e) => update('search', e.target.value)}
            />
          </label>
          <select
            aria-label="Filtrar por status"
            value={params.get('status') ?? ''}
            onChange={(e) => update('status', e.target.value)}
          >
            <option value="">Todos os estados</option>
            {Object.entries(statusLabels).map(([key, label]) => (
              <option key={key} value={key}>
                {label} ({key})
              </option>
            ))}
          </select>
          <label className="sort">
            <ArrowDownWideNarrow size={15} />
            <select
              aria-label="Ordenar por última atividade"
              value={apiParams.get('order')!}
              onChange={(e) => update('order', e.target.value)}
            >
              <option value="desc">Mais recentes</option>
              <option value="asc">Mais antigas</option>
            </select>
          </label>
        </div>
        {runs.isError && <ErrorState error={runs.error} retry={runs.refetch} />}
        {runs.isPending ? (
          <Loading />
        ) : (
          runs.data && <RunTable runs={runs.data.items} />
        )}
        {runs.data && (
          <div className="pagination">
            <span>
              {runs.data.total
                ? `${offset + 1}–${Math.min(offset + 15, runs.data.total)}`
                : 0}{' '}
              de {runs.data.total} execuções
            </span>
            <div>
              <Button
                size="sm"
                aria-label="Página anterior"
                disabled={offset === 0}
                onClick={() =>
                  update('offset', String(Math.max(0, offset - 15)))
                }
              >
                <ChevronLeft size={14} />
              </Button>
              <Button
                size="sm"
                aria-label="Próxima página"
                disabled={offset + 15 >= runs.data.total}
                onClick={() => update('offset', String(offset + 15))}
              >
                <ChevronRight size={14} />
              </Button>
            </div>
          </div>
        )}
      </section>
      <div className="info-note">
        A duração é calculada entre início e término registrados. Testes indicam
        o último resultado disponível.
      </div>
    </>
  )
}
