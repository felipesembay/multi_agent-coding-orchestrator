import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { routes } from '../app/router'
import type { Project, ProjectRequest } from '../types'
const project: Project = {
  id: 'project-filmes',
  name: 'Sistema de Recomendação de Filmes',
  description: 'Recomendações personalizadas',
  objectives: 'API com testes',
  repo_path: '/allowed/filmes',
  repository_id: 'repo-one',
  state: 'active',
  created_at: '2026-11-05 12:00:00',
  updated_at: '2026-11-05 12:00:00',
  request_count: 0,
}
function setup(
  path = '/',
  options: {
    empty?: boolean
    roots?: boolean
    fail?: boolean
    denied?: boolean
  } = {},
) {
  let saved = !options.empty
  const requests: ProjectRequest[] = []
  const fetcher = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input),
        method = init?.method ?? 'GET'
      const response = (data: unknown, status = 200) => ({
        ok: status < 400,
        status,
        json: async () => data,
      })
      if (url === '/api/health') return response({ status: 'ok' })
      if (options.fail) return response({}, 503)
      if (url === '/api/session')
        return response({ csrf_token: 'session-token' })
      if (url === '/api/project-policy')
        return response({
          roots:
            options.roots === false
              ? []
              : [{ path: '/allowed', available: true }],
          git_available: true,
          preview_ttl_seconds: 600,
        })
      if (url === '/api/projects/preview')
        return options.denied
          ? response({ detail: 'Diretório não autorizado.' }, 403)
          : response({
              preview_token: 'preview-token',
              project: JSON.parse(String(init?.body)),
              actions: ['Criar diretório', 'Criar commit inicial local'],
              expires_in_seconds: 600,
            })
      if (url === '/api/projects' && method === 'POST') {
        saved = true
        return response(project, 201)
      }
      if (url === '/api/projects') return response(saved ? [project] : [])
      if (url === '/api/projects/project-filmes/requests') {
        if (method === 'POST') {
          const body = JSON.parse(String(init?.body))
          const value = {
            ...body,
            id: 'request-one',
            project_id: project.id,
            created_at: project.created_at,
            state: 'submitted',
          }
          requests.push(value)
          return response(value, 201)
        }
        return response(requests)
      }
      if (url === '/api/projects/project-filmes/runs') return response([])
      if (url === '/api/projects/project-filmes') return response(project)
      throw new Error(`Unexpected URL ${url}`)
    },
  )
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
  return { fetcher, router, requests }
}
describe('project workspace', () => {
  it('uses projects as the homepage and opens the named workspace', async () => {
    const { router } = setup()
    await userEvent.click(
      await screen.findByRole('link', {
        name: /Sistema de Recomendação de Filmes/,
      }),
    )
    expect(router.state.location.pathname).toBe('/projects/project-filmes')
    expect(
      await screen.findByRole('heading', { name: 'O que vamos desenvolver?' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Iniciar execução/ }),
    ).not.toBeInTheDocument()
  })
  it('shows an actionable empty state and filters by project name', async () => {
    setup()
    await screen.findByRole('heading', { name: project.name })
    fireEvent.change(screen.getByRole('textbox', { name: 'Buscar projetos' }), {
      target: { value: 'outra coisa' },
    })
    expect(
      await screen.findByText('Nenhum projeto com esses filtros'),
    ).toBeInTheDocument()
  })
  it('creates only after preview and explicit confirmation', async () => {
    const { fetcher, router } = setup('/projects/new', { empty: true })
    await screen.findByText('Diretórios autorizados')
    await userEvent.click(
      screen.getByRole('radio', { name: /Criar projeto novo/ }),
    )
    fireEvent.change(screen.getByRole('textbox', { name: 'Nome do projeto' }), {
      target: { value: project.name },
    })
    fireEvent.change(
      screen.getByRole('textbox', { name: /Caminho absoluto/ }),
      { target: { value: '/allowed/filmes' } },
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Revisar projeto' }),
    )
    await screen.findByRole('heading', { name: 'Revise antes de confirmar' })
    const confirm = screen.getByRole('button', {
      name: 'Confirmar e criar projeto',
    })
    expect(confirm).toBeDisabled()
    expect(
      fetcher.mock.calls.some(
        ([url, init]) => url === '/api/projects' && init?.method === 'POST',
      ),
    ).toBe(false)
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(confirm)
    await screen.findByRole('heading', { name: 'O que vamos desenvolver?' })
    expect(router.state.location.pathname).toBe('/projects/project-filmes')
    const write = fetcher.mock.calls.find(
      ([url, init]) => url === '/api/projects' && init?.method === 'POST',
    )!
    expect(JSON.parse(String(write[1]?.body))).toEqual({
      preview_token: 'preview-token',
      confirmed: true,
    })
    expect(write[1]?.headers).toHaveProperty(
      'X-Orchestrator-CSRF',
      'session-token',
    )
  })
  it('saves a natural language request and displays it in the project history', async () => {
    const { requests } = setup('/projects/project-filmes')
    await screen.findByRole('heading', { name: 'O que vamos desenvolver?' })
    fireEvent.change(
      screen.getByRole('textbox', { name: 'Título da solicitação' }),
      { target: { value: 'Criar API' } },
    )
    fireEvent.change(
      screen.getByRole('textbox', { name: 'Requisitos em linguagem natural' }),
      {
        target: {
          value: 'Crie FastAPI com PostgreSQL, testes e documentação.',
        },
      },
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Salvar solicitação' }),
    )
    expect(await screen.findByText('Criar API')).toBeInTheDocument()
    expect(requests[0].content).toContain('PostgreSQL')
    expect(
      screen.getByRole('textbox', { name: 'Título da solicitação' }),
    ).toHaveValue('')
  })
  it('blocks creation with setup guidance when no directory is authorized', async () => {
    setup('/projects/new', { roots: false })
    expect(
      await screen.findByText('Configure o acesso local'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Revisar projeto' }),
    ).toBeDisabled()
  })
  it('shows server validation errors instead of pretending to create a project', async () => {
    const { fetcher } = setup('/projects/new', { denied: true })
    await screen.findByText('Diretórios autorizados')
    fireEvent.change(screen.getByRole('textbox', { name: 'Nome do projeto' }), {
      target: { value: project.name },
    })
    fireEvent.change(
      screen.getByRole('textbox', { name: /Caminho absoluto/ }),
      { target: { value: '/forbidden/filmes' } },
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Revisar projeto' }),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Diretório não autorizado.',
    )
    expect(
      fetcher.mock.calls.some(
        ([url, init]) => url === '/api/projects' && init?.method === 'POST',
      ),
    ).toBe(false)
  })
  it('reports API errors on the project list', async () => {
    setup('/', { fail: true })
    expect(await screen.findByRole('alert')).toHaveTextContent('503')
  })
  it('loads project requests independently when returning to the workspace', async () => {
    const { fetcher } = setup('/projects/project-filmes')
    await screen.findByRole('heading', { name: 'O que vamos desenvolver?' })
    await waitFor(() =>
      expect(
        fetcher.mock.calls.some(
          ([url]) => url === '/api/projects/project-filmes/requests',
        ),
      ).toBe(true),
    )
  })
})
