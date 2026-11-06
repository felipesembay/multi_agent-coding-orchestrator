import {
  AlertCircle,
  ArrowRight,
  FolderGit2,
  Inbox,
  RefreshCw,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'
import type { Run } from '../types'
import { date, duration, statusLabels } from '../lib/events'
import { Button } from './ui/button'
export function Status({ status }: { status: string }) {
  return (
    <span
      className={`status status-${['queued', 'interrupted', 'running', 'blocked', 'error', 'failed', 'ready_for_human_review', 'completed', 'success', 'succeeded'].includes(status) ? status : 'unknown'}`}
    >
      <span />
      {statusLabels[status] ?? status}
    </span>
  )
}
export function Empty({
  title = 'Nenhuma execução encontrada',
  children,
}: {
  title?: string
  children?: ReactNode
}) {
  return (
    <div className="empty">
      <Inbox size={28} />
      <h3>{title}</h3>
      <p>{children ?? 'As execuções registradas pelo CLI aparecerão aqui.'}</p>
    </div>
  )
}
export function Loading() {
  return (
    <div role="status" aria-label="Carregando" className="skeletons">
      {[1, 2, 3].map((i) => (
        <div className="skeleton" key={i} />
      ))}
      <span className="sr-only">Carregando dados…</span>
    </div>
  )
}
export function ErrorState({
  error,
  retry,
}: {
  error: Error | null
  retry: () => unknown
}) {
  return (
    <div role="alert" className="error-panel">
      <AlertCircle size={20} />
      <div>
        <strong>Não foi possível atualizar os dados</strong>
        <p>
          {error?.message ?? 'Falha de conexão.'} Verifique o backend em
          127.0.0.1:8765.
        </p>
      </div>
      <Button onClick={() => void retry()}>
        <RefreshCw size={14} />
        Tentar novamente
      </Button>
    </div>
  )
}
export function SectionTitle({
  title,
  subtitle,
  action,
}: {
  title: string
  subtitle?: string
  action?: ReactNode
}) {
  return (
    <div className="section-title">
      <div>
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}
export function RunTable({ runs }: { runs: Run[] }) {
  if (!runs.length) return <Empty />
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Execução / repositório</th>
            <th>Status</th>
            <th>Início</th>
            <th>Última atividade</th>
            <th>Duração</th>
            <th>Tarefas</th>
            <th>Testes</th>
            <th>
              <span className="sr-only">Detalhes</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.run_id}>
              <td>
                <Link
                  className="run-link"
                  to={`/executions/${encodeURIComponent(run.run_id)}`}
                >
                  {run.run_id}
                </Link>
                <span className="repo" title={run.repo ?? undefined}>
                  <FolderGit2 size={12} />
                  {run.repo?.split('/').filter(Boolean).pop() ??
                    'Repositório não registrado'}
                </span>
              </td>
              <td>
                <Status status={run.status} />
              </td>
              <td className="numeric muted">{date(run.started_at)}</td>
              <td className="numeric muted">{date(run.last_event)}</td>
              <td className="numeric">{duration(run.duration_seconds)}</td>
              <td>{run.task_count ?? '—'}</td>
              <td>
                <TestBadge passed={run.tests_passed} />
              </td>
              <td>
                <Link
                  aria-label={`Abrir ${run.run_id}`}
                  to={`/executions/${encodeURIComponent(run.run_id)}`}
                  className="icon-link"
                >
                  <ArrowRight size={16} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
export function TestBadge({ passed }: { passed: unknown }) {
  return (
    <span
      className={
        passed === true ? 'text-green' : passed === false ? 'text-red' : 'muted'
      }
    >
      {passed === true
        ? 'Aprovados'
        : passed === false
          ? 'Reprovados'
          : 'Não registrado'}
    </span>
  )
}
export function RawData({ value }: { value: unknown }) {
  return (
    <details className="raw">
      <summary>Dados originais · JSON</summary>
      <pre>
        {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
      </pre>
    </details>
  )
}
