import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { WorkflowsPage, WorkflowEditorPage } from '../features/Workflows'

function definition(name = 'Meu fluxo') {
  return {
    schema_version: 1,
    name,
    steps: [
      { id: 'plan', type: 'plan', role: 'planner', requires: ['planning'] },
      {
        id: 'impl',
        type: 'implement',
        role: 'implementer',
        requires: ['code_edit'],
        per_task: true,
        max_attempts: 3,
      },
      {
        id: 'tests',
        type: 'test',
        per_task: true,
        command_profile: 'server_default',
      },
      {
        id: 'review',
        type: 'review',
        role: 'reviewer',
        requires: ['review'],
        per_task: true,
        on_reject: 'impl',
      },
    ],
    limits: { max_total_steps: 200, max_duration_s: 14400, budget_usd: null },
    approval: {
      require_tests: true,
      require_reviewer: true,
      human_gate_after_plan: false,
    },
  }
}

function setup(
  path = '/workflows/new',
  options: {
    readonly?: boolean
    validationDown?: boolean
    catalogDown?: boolean
    noTests?: boolean
  } = {},
) {
  const versions = [{ id: 'v1', version: 1, definition: definition() }]
  if (options.noTests) {
    versions[0].definition.steps = versions[0].definition.steps.filter(
      (s) => s.type !== 'test',
    )
    versions[0].definition.approval.require_tests = false
  }
  let copy: {
    id: string
    name: string
    read_only: boolean
    latest_version: (typeof versions)[0]
  } | null = null
  const fetcher = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const result = (data: unknown, status = 200) => ({
        ok: status < 400,
        status,
        json: async () => data,
      })
      const body = init?.body ? JSON.parse(String(init.body)) : null
      if (options.catalogDown && url === '/api/workflows')
        throw new Error('temporarily unavailable')
      if (url === '/api/session') return result({ csrf_token: 'token' })
      if (url === '/api/workflows/validate') {
        if (options.validationDown)
          return result({ detail: 'Unavailable' }, 503)
        if (
          body.definition.steps.some(
            (s: { max_attempts?: number }) => s.max_attempts === 0,
          )
        )
          return result(
            {
              detail: [
                {
                  loc: [
                    'body',
                    'definition',
                    'steps',
                    1,
                    'implement',
                    'max_attempts',
                  ],
                  msg: 'Must be at least 1',
                  type: 'greater_than_equal',
                },
              ],
            },
            422,
          )
        return result({
          valid: true,
          executable: null,
          errors: [],
          validation_scope: 'definition',
        })
      }
      if (url === '/api/workflow-presets')
        return result([
          {
            id: 'default-v2',
            title: 'Preset A',
            available: false,
            blocked_by: [],
            read_only: true,
            errors: ['Permissões pendentes'],
          },
          {
            id: 'openrouter-plan',
            title: 'Preset B',
            available: false,
            blocked_by: ['V2-PROV-001'],
            read_only: true,
            errors: ['Integração pendente'],
          },
        ])
      if (url === '/api/workflows' && init?.method === 'POST') {
        const saved = body.definition ?? definition(body.name)
        copy = {
          id: 'wf-created',
          name: saved.name,
          read_only: false,
          latest_version: { id: 'v-created', version: 1, definition: saved },
        }
        return result(copy, 201)
      }
      if (url === '/api/workflows')
        return result([
          {
            id: 'wf1',
            name: versions.at(-1)!.definition.name,
            description: '',
            read_only: !!options.readonly,
            latest_version: versions.at(-1),
          },
          ...(copy ? [copy] : []),
        ])
      if (url === '/api/workflows/wf1/versions' && init?.method === 'POST') {
        const next = {
          id: `v${versions.length + 1}`,
          version: versions.length + 1,
          definition: body.definition,
        }
        versions.push(next)
        return result(next, 201)
      }
      if (url === '/api/workflows/wf1/versions') return result(versions)
      if (url === '/api/workflows/wf-created/versions')
        return result(copy ? [copy.latest_version] : [])
      throw new Error(`Unexpected ${url}`)
    },
  )
  vi.stubGlobal('fetch', fetcher)
  const router = createMemoryRouter(
    [
      { path: '/workflows', element: <WorkflowsPage /> },
      { path: '/workflows/new', element: <WorkflowEditorPage /> },
      { path: '/workflows/:workflowId', element: <WorkflowEditorPage /> },
    ],
    { initialEntries: [path] },
  )
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { fetcher, router, versions, client }
}

describe('workflow list editor', () => {
  it('creates a structurally validated workflow with an optional stage', async () => {
    const { fetcher, router } = setup()
    const name = await screen.findByRole('textbox', {
      name: 'Nome do workflow',
    })
    await userEvent.clear(name)
    await userEvent.type(name, 'Fluxo novo')
    await userEvent.click(
      screen.getByRole('button', { name: 'Adicionar etapa' }),
    )
    expect(screen.getByText('document-1')).toBeInTheDocument()
    const save = screen.getByRole('button', { name: 'Salvar workflow' })
    await waitFor(() => expect(save).toBeEnabled())
    expect(fetcher.mock.calls.some(([url]) => url === '/api/workflows')).toBe(
      false,
    )
    await userEvent.click(save)
    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/workflows/wf-created'),
    )
    const write = fetcher.mock.calls.find(
      ([url, init]) => url === '/api/workflows' && init?.method === 'POST',
    )!
    const body = JSON.parse(String(write[1]?.body))
    expect(body.definition.name).toBe('Fluxo novo')
    expect(body.definition.steps.at(-1).type).toBe('document')
    expect(body.bindings).toBeUndefined()
    expect(
      fetcher.mock.calls.some(([url]) => String(url).includes('/runs')),
    ).toBe(false)
  })
  it('blocks stale or invalid drafts and shows validation per field', async () => {
    const { fetcher } = setup()
    const attempts = await screen.findByRole('spinbutton', {
      name: 'Tentativas para impl',
    })
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Salvar workflow' }),
      ).toBeEnabled(),
    )
    fireEvent.change(attempts, { target: { value: '0' } })
    expect(
      screen.getByRole('button', { name: 'Salvar workflow' }),
    ).toBeDisabled()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /Tentativas|tentativas/,
    )
    expect(fetcher.mock.calls.some(([url]) => url === '/api/workflows')).toBe(
      false,
    )
  })
  it('appends a new immutable version and keeps the previous one unchanged', async () => {
    const { fetcher, router, versions } = setup('/workflows/wf1')
    const name = await screen.findByRole('textbox', {
      name: 'Nome do workflow',
    })
    await userEvent.clear(name)
    await userEvent.type(name, 'Fluxo versão dois')
    expect(
      screen.getByRole('combobox', { name: 'Versão do workflow' }),
    ).toBeDisabled()
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Salvar nova versão' }),
      ).toBeEnabled(),
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Salvar nova versão' }),
    )
    await waitFor(() =>
      expect(router.state.location.search).toContain('version=v2'),
    )
    expect(versions).toHaveLength(2)
    expect(versions[0].definition.name).toBe('Meu fluxo')
    expect(versions[1].definition.name).toBe('Fluxo versão dois')
    expect(
      fetcher.mock.calls.some(
        ([url, init]) =>
          url === '/api/workflows/wf1/versions' && init?.method === 'POST',
      ),
    ).toBe(true)
  })
  it('preserves readonly sources while allowing a user copy', async () => {
    const { fetcher, router } = setup('/workflows/wf1', { readonly: true })
    expect(
      await screen.findByRole('textbox', { name: 'Nome do workflow' }),
    ).toBeDisabled()
    expect(
      screen.queryByRole('button', { name: 'Salvar nova versão' }),
    ).not.toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Criar cópia' })).toBeEnabled(),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Criar cópia' }))
    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/workflows/wf-created'),
    )
    expect(
      await screen.findByRole('textbox', { name: 'Nome do workflow' }),
    ).toBeEnabled()
    expect(
      fetcher.mock.calls.some(
        ([url, init]) =>
          url === '/api/workflows/wf1/versions' && init?.method === 'POST',
      ),
    ).toBe(false)
  })
  it('clones an editable system template without enabling unavailable integrations', async () => {
    const { fetcher, router } = setup('/workflows')
    const clone = await screen.findByRole('button', {
      name: 'Criar cópia de Preset A',
    })
    expect(clone).toBeEnabled()
    expect(
      screen.getByRole('button', { name: 'Criar cópia de Preset B' }),
    ).toBeDisabled()
    await userEvent.click(clone)
    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/workflows/wf-created'),
    )
    const write = fetcher.mock.calls.find(
      ([url, init]) => url === '/api/workflows' && init?.method === 'POST',
    )!
    expect(JSON.parse(String(write[1]?.body)).preset_id).toBe('default-v2')
  })
  it('restricts reordering and supports discarding edits', async () => {
    setup('/workflows/wf1')
    await screen.findByRole('textbox', { name: 'Nome do workflow' })
    expect(
      screen.getByRole('button', { name: 'Mover plan para baixo' }),
    ).toBeDisabled()
    await userEvent.click(
      screen.getByRole('button', { name: 'Mover review para cima' }),
    )
    expect(
      screen.getByRole('button', { name: 'Mover review para cima' }),
    ).toBeDisabled()
    await userEvent.click(
      screen.getByRole('button', { name: 'Descartar edição' }),
    )
    const stages = screen.getByRole('list', { name: 'Etapas do workflow' })
    expect(
      within(stages)
        .getAllByRole('listitem')
        .map((item) => item.getAttribute('data-step-id')),
    ).toEqual(['plan', 'impl', 'tests', 'review'])
  })
  it('never saves when validation is unavailable', async () => {
    setup('/workflows/new', { validationDown: true })
    expect(await screen.findByRole('alert')).toHaveTextContent(/validar/)
    expect(
      screen.getByRole('button', { name: 'Salvar workflow' }),
    ).toBeDisabled()
  })
  it('keeps the selected version and unsaved draft when new versions arrive', async () => {
    const { client, versions, router } = setup('/workflows/wf1')
    const name = await screen.findByRole('textbox', {
      name: 'Nome do workflow',
    })
    await userEvent.clear(name)
    await userEvent.type(name, 'Rascunho local')
    versions.push({
      id: 'remote-v2',
      version: 2,
      definition: definition('Outra sessão'),
    })
    await client.invalidateQueries({ queryKey: ['workflow-versions', 'wf1'] })
    await waitFor(() =>
      expect(
        screen.getByRole('option', { name: 'Versão 2' }),
      ).toBeInTheDocument(),
    )
    expect(name).toHaveValue('Rascunho local')
    expect(router.state.location.search).toBe('?version=v1')
  })
  it('preserves edits through a failed background refresh and recovery', async () => {
    const options = { catalogDown: false }
    const { client } = setup('/workflows/wf1', options)
    const name = await screen.findByRole('textbox', {
      name: 'Nome do workflow',
    })
    await userEvent.clear(name)
    await userEvent.type(name, 'Não perder')
    options.catalogDown = true
    await client.invalidateQueries({ queryKey: ['workflows'] })
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'rascunho foi preservado',
    )
    expect(
      screen.getByRole('textbox', { name: 'Nome do workflow' }),
    ).toHaveValue('Não perder')
    options.catalogDown = false
    await client.invalidateQueries({ queryKey: ['workflows'] })
    await waitFor(() =>
      expect(screen.queryByRole('alert')).not.toBeInTheDocument(),
    )
    expect(
      screen.getByRole('textbox', { name: 'Nome do workflow' }),
    ).toHaveValue('Não perder')
  })
  it('enables the tests policy when adding the first test to an existing definition', async () => {
    const { fetcher } = setup('/workflows/wf1', { noTests: true })
    await screen.findByRole('textbox', { name: 'Nome do workflow' })
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Etapa opcional' }),
      'test',
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Adicionar etapa' }),
    )
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Salvar nova versão' }),
      ).toBeEnabled(),
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Salvar nova versão' }),
    )
    const write = fetcher.mock.calls.find(
      ([url, init]) =>
        url === '/api/workflows/wf1/versions' && init?.method === 'POST',
    )!
    expect(
      JSON.parse(String(write[1]?.body)).definition.approval.require_tests,
    ).toBe(true)
  })
})
