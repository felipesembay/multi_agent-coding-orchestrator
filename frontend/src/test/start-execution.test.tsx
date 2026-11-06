import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { StartExecution } from '../features/StartExecution'
import type { ExecutionPreflight, Project, ProjectRequest } from '../types'
const project: Project = {
  id: 'project-existing',
  name: 'Task Manager API',
  description: '',
  objectives: '',
  repo_path: '/authorized/task_manager',
  repository_id: 'repo-one',
  state: 'active',
  created_at: '',
  updated_at: '',
}
const task: ProjectRequest = {
  id: 'request-existing',
  project_id: project.id,
  title: 'Criar uma API REST para gerenciar tarefas pessoais.',
  content: 'Criar endpoints para tarefas com testes.',
  state: 'submitted',
  created_at: '',
}
const config: ExecutionPreflight = {
  ready: true,
  configuration_digest: 'a'.repeat(64),
  errors: [],
  worker: { online: true, heartbeat: 0 },
  configuration: {
    planner: 'claude',
    implementer: 'antigravity',
    reviewer: 'codex',
    planner_model: null,
    implementer_model: 'configured-model',
    planner_fallback_model: 'configured-fallback',
    test_command: 'python -m pytest -q',
    worktree_base: '/authorized/worktrees',
    max_attempts: 3,
    agent_timeout: 900,
    test_timeout: 300,
  },
}
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function () {
    this.open = false
  }
})
function setup(
  options: { offline?: boolean; fail?: boolean; pending?: boolean } = {},
) {
  let failed = false
  const fetcher = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const result = (data: unknown, status = 200) => ({
        ok: status < 400,
        status,
        json: async () => data,
      })
      if (url.endsWith('/execution-config'))
        return result(
          options.offline
            ? {
                ...config,
                ready: false,
                errors: ['Worker offline. Inicie o worker.'],
                worker: { online: false },
              }
            : config,
        )
      if (url === '/api/session') return result({ csrf_token: 'csrf-token' })
      if (
        url.endsWith(`/requests/${task.id}/runs`) &&
        init?.method === 'POST'
      ) {
        if (options.pending) return new Promise(() => {})
        if (options.fail && !failed) {
          failed = true
          return result(
            { detail: 'Não foi possível registrar a execução.' },
            503,
          )
        }
        return result(
          {
            run_id: 'run-managed',
            status: 'queued',
            project_id: project.id,
            request_id: task.id,
          },
          202,
        )
      }
      throw new Error(`Unexpected URL ${url}`)
    },
  )
  vi.stubGlobal('fetch', fetcher)
  const close = vi.fn()
  const router = createMemoryRouter([
    {
      path: '/',
      element: <StartExecution project={project} task={task} onClose={close} />,
    },
    { path: '/executions/:id', element: <h1>Acompanhamento da execução</h1> },
  ])
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { fetcher, router, close }
}
describe('start execution confirmation', () => {
  it('shows the existing project, request and actual configuration without starting anything', async () => {
    const { fetcher } = setup()
    await screen.findByText('configured-model', { exact: false })
    expect(screen.getByText('Task Manager API')).toBeInTheDocument()
    expect(screen.getByText(task.title)).toBeInTheDocument()
    expect(screen.getByText('python -m pytest -q')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Confirmar e iniciar' }),
    ).toBeDisabled()
    expect(fetcher.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(
      false,
    )
  })
  it('posts only an explicit confirmation and navigates after acceptance', async () => {
    const { fetcher, router } = setup()
    await screen.findByText('configured-model', { exact: false })
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(
      screen.getByRole('button', { name: 'Confirmar e iniciar' }),
    )
    await screen.findByRole('heading', { name: 'Acompanhamento da execução' })
    expect(router.state.location.pathname).toBe('/executions/run-managed')
    const posted = fetcher.mock.calls.find(
      ([, init]) => init?.method === 'POST',
    )!
    const body = JSON.parse(String(posted[1]?.body))
    expect(body.confirmed).toBe(true)
    expect(body.configuration_digest).toBe(config.configuration_digest)
    expect(body.idempotency_key.length).toBeGreaterThan(16)
    expect(body.test_command).toBeUndefined()
    expect(posted[0]).toContain('/request-existing/runs')
  })
  it('keeps the same idempotency key when retrying an uncertain response', async () => {
    const { fetcher } = setup({ fail: true })
    await screen.findByText('configured-model', { exact: false })
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(
      screen.getByRole('button', { name: 'Confirmar e iniciar' }),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível registrar',
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Confirmar e iniciar' }),
    )
    await screen.findByRole('heading', { name: 'Acompanhamento da execução' })
    const writes = fetcher.mock.calls.filter(
      ([, init]) => init?.method === 'POST',
    )
    expect(JSON.parse(String(writes[0][1]?.body)).idempotency_key).toBe(
      JSON.parse(String(writes[1][1]?.body)).idempotency_key,
    )
  })
  it('blocks a real start while worker preflight is failing', async () => {
    const { fetcher } = setup({ offline: true })
    expect(await screen.findByRole('alert')).toHaveTextContent('Worker offline')
    expect(screen.getByRole('checkbox')).toBeDisabled()
    expect(
      screen.getByRole('button', { name: 'Confirmar e iniciar' }),
    ).toBeDisabled()
    expect(fetcher.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(
      false,
    )
  })
  it('prevents duplicate clicks while the submission is pending', async () => {
    const { fetcher } = setup({ pending: true })
    await screen.findByText('configured-model', { exact: false })
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(
      screen.getByRole('button', { name: 'Confirmar e iniciar' }),
    )
    const button = await screen.findByRole('button', {
      name: 'Registrando execução…',
    })
    expect(button).toBeDisabled()
    await userEvent.click(button)
    await waitFor(() =>
      expect(
        fetcher.mock.calls.filter(([, init]) => init?.method === 'POST'),
      ).toHaveLength(1),
    )
  })
})
