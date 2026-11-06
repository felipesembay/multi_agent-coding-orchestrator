import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { routes } from '../app/router'
import type { RawEvent, Run } from '../types'
const run: Run = {
  run_id: 'run-real',
  repo: '/local/project',
  worktree: '/local/worktree',
  status: 'ready_for_human_review',
  started_at: '2026-11-05 12:00:00',
  finished_at: '2026-11-05 12:02:00',
  last_event: '2026-11-05 12:02:00',
  duration_seconds: 120,
  task_count: 1,
  tests_passed: true,
  current_stage: 'finished',
  attempts: 1,
}
const events: RawEvent[] = [
  {
    id: 1,
    at: run.started_at!,
    stage: 'started',
    payload: '{"repo":"/local/project"}',
  },
  { id: 2, at: run.finished_at!, stage: 'custom-event', payload: '{malformed' },
]
function setup(
  path = '/executions',
  options: { empty?: boolean; fail?: boolean; pending?: boolean } = {},
) {
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url === '/api/health')
      return { ok: true, json: async () => ({ status: 'ok' }) }
    if (options.pending) return new Promise(() => {})
    if (options.fail) return { ok: false, status: 503 }
    let data: unknown
    if (url.startsWith('/api/runs?'))
      data = {
        items: options.empty ? [] : [run],
        total: options.empty ? 0 : 1,
        offset: 0,
        limit: 15,
      }
    else if (url === '/api/runs/run-real') data = { ...run, events }
    else if (url === '/api/overview')
      data = {
        total: 1,
        counts: { ready_for_human_review: 1 },
        average_duration_seconds: 120,
        duration_sample_count: 1,
        activity: [],
      }
    else throw new Error(`Unexpected URL ${url}`)
    return { ok: true, json: async () => data }
  })
  vi.stubGlobal('fetch', fetcher)
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router, fetcher }
}
describe('dashboard integration', () => {
  it('renders actual runs and navigates to selected execution', async () => {
    const { router } = setup()
    await userEvent.click(await screen.findByRole('link', { name: 'run-real' }))
    await screen.findByRole('heading', { name: 'Timeline de eventos' })
    expect(router.state.location.pathname).toBe('/executions/run-real')
    expect(screen.getByText('/local/worktree')).toBeInTheDocument()
    expect(screen.getByText('Revisão humana')).toBeInTheDocument()
  })
  it('shows loading until the API responds', async () => {
    setup('/executions', { pending: true })
    expect(
      await screen.findByRole('status', { name: 'Carregando' }),
    ).toBeInTheDocument()
  })
  it('shows empty responses', async () => {
    setup('/executions', { empty: true })
    expect(
      await screen.findByText('Nenhuma execução encontrada'),
    ).toBeInTheDocument()
  })
  it('offers retry on API errors', async () => {
    const { fetcher } = setup('/executions', { fail: true })
    expect(await screen.findByRole('alert')).toHaveTextContent('503')
    await userEvent.click(
      screen.getByRole('button', { name: 'Tentar novamente' }),
    )
    await waitFor(() =>
      expect(
        fetcher.mock.calls.filter(([url]) =>
          String(url).startsWith('/api/runs?'),
        ).length,
      ).toBeGreaterThan(1),
    )
  })
  it('preserves unfamiliar events and malformed data in the timeline', async () => {
    setup('/executions/run-real')
    const summary = await screen.findByText('custom-event')
    await userEvent.click(summary)
    expect(
      screen.getByText(/Não foi possível interpretar este payload/),
    ).toBeVisible()
    await userEvent.click(
      within(summary.closest('details')!).getByText('Dados originais · JSON'),
    )
    expect(screen.getByText('{malformed')).toBeVisible()
  })
  it('sends status, search and sorting filters to the backend', async () => {
    const { fetcher } = setup()
    await screen.findByRole('link', { name: 'run-real' })
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Filtrar por status' }),
      { target: { value: 'blocked' } },
    )
    fireEvent.change(
      screen.getByRole('textbox', { name: 'Buscar por Run ID' }),
      { target: { value: 'run-abc' } },
    )
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Ordenar por última atividade' }),
      { target: { value: 'asc' } },
    )
    await waitFor(() =>
      expect(
        fetcher.mock.calls.some(
          ([url]) =>
            String(url).includes('status=blocked') &&
            String(url).includes('search=run-abc') &&
            String(url).includes('order=asc'),
        ),
      ).toBe(true),
    )
  })
  it('uses the selected run in agent monitoring', async () => {
    setup('/agents?run=run-real')
    expect(
      await screen.findByRole('heading', { name: 'Planner' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('combobox', { name: 'Selecionar execução' }),
    ).toHaveValue('run-real')
    expect(screen.getAllByText('Provider histórico')).toHaveLength(3)
  })
  it('separates human review from completed totals', async () => {
    setup('/overview')
    expect(
      await screen.findByText('1 execuções com início e término'),
    ).toBeInTheDocument()
    const metric = screen.getByText('Concluídas').closest('article')!
    expect(metric).toHaveTextContent('0')
    expect(
      screen.getByRole('heading', { name: 'Execuções recentes' }),
    ).toBeInTheDocument()
  })
})
