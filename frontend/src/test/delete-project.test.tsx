import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { DeleteProject } from '../features/DeleteProject'
import type { Project } from '../types'
const project: Project = {
  id: 'project-failed',
  name: 'Projeto com erro',
  description: '',
  objectives: '',
  repo_path: '/authorized/project',
  repository_id: 'repo-one',
  state: 'active',
  created_at: '',
  updated_at: '',
}
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function () {
    this.open = false
  }
})
function setup(options: { busy?: boolean; fail?: boolean } = {}) {
  const fetcher = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === '/api/session')
        return { ok: true, json: async () => ({ csrf_token: 'csrf-token' }) }
      if (init?.method === 'DELETE')
        return {
          ok: !options.fail,
          status: options.fail ? 409 : 200,
          json: async () =>
            options.fail
              ? { detail: 'Execução em andamento.' }
              : { deleted: true },
        }
      throw new Error(`Unexpected URL ${input}`)
    },
  )
  vi.stubGlobal('fetch', fetcher)
  const close = vi.fn()
  const router = createMemoryRouter(
    [
      {
        path: '/delete',
        element: (
          <DeleteProject
            project={project}
            busy={options.busy ?? false}
            onClose={close}
          />
        ),
      },
      { path: '/', element: <h1>Projetos</h1> },
    ],
    { initialEntries: ['/delete'] },
  )
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
describe('project deletion', () => {
  it('requires typing the current name and performs a protected DELETE before navigating', async () => {
    const { fetcher, router } = setup()
    expect(
      screen.getByRole('button', { name: 'Confirmar exclusão' }),
    ).toBeDisabled()
    expect(screen.getByText(/Os arquivos do repositório/)).toBeInTheDocument()
    expect(fetcher).not.toHaveBeenCalled()
    fireEvent.change(
      screen.getByRole('textbox', {
        name: 'Digite o nome do projeto para confirmar',
      }),
      { target: { value: project.name } },
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Confirmar exclusão' }),
    )
    await screen.findByRole('heading', { name: 'Projetos' })
    expect(router.state.location.pathname).toBe('/')
    const write = fetcher.mock.calls.find(
      ([, init]) => init?.method === 'DELETE',
    )!
    expect(JSON.parse(String(write[1]?.body))).toEqual({
      confirmed: true,
      project_name: project.name,
    })
    expect(write[1]?.headers).toHaveProperty(
      'X-Orchestrator-CSRF',
      'csrf-token',
    )
  })
  it('blocks active runs and allows cancelling without a write', async () => {
    const { fetcher, close } = setup({ busy: true })
    expect(screen.getByRole('alert')).toHaveTextContent('processo órfão')
    expect(
      screen.getByRole('button', { name: 'Confirmar exclusão' }),
    ).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(close).toHaveBeenCalledOnce()
    expect(fetcher).not.toHaveBeenCalled()
  })
  it('keeps the dialog open and displays a server conflict', async () => {
    setup({ fail: true })
    fireEvent.change(
      screen.getByRole('textbox', {
        name: 'Digite o nome do projeto para confirmar',
      }),
      { target: { value: project.name } },
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Confirmar exclusão' }),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Execução em andamento.',
    )
    expect(
      screen.queryByRole('heading', { name: 'Projetos' }),
    ).not.toBeInTheDocument()
  })
})
