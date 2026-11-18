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
  options: {
    offline?: boolean
    fail?: boolean
    pending?: boolean
    customWorkflow?: boolean
    presetReady?: boolean
    presetTrio?: boolean
    prototypeStep?: boolean
  } = {},
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
      const definition = {
        schema_version: 1,
        name: 'Meu workflow',
        steps: [
          { id: 'plan', type: 'plan', role: 'planner', requires: ['planning'] },
          {
            id: options.prototypeStep ? 'constructor' : 'impl',
            type: 'implement',
            role: 'implementer',
            requires: ['code_edit'],
            per_task: true,
          },
          {
            id: 'review',
            type: 'review',
            role: 'reviewer',
            requires: ['review'],
            per_task: true,
          },
        ],
      }
      const version = (id: string, number: number) => ({
        id,
        version: number,
        definition,
      })
      const hints = options.presetTrio
        ? {
            plan: {
              provider_config_id: 'pc-claude',
              permission: 'read_only',
              model: null,
            },
            impl: {
              provider_config_id: 'pc-codex',
              permission: 'workspace_write',
              model: null,
            },
            review: {
              provider_config_id: 'pc-agy',
              permission: 'read_only',
              model: null,
            },
          }
        : {}
      if (url === '/api/workflow-presets')
        return result([
          {
            id: 'legacy-v1',
            title: 'Legacy v1',
            execution_mode: 'legacy',
            available: true,
            errors: [],
            default_for_cli: true,
          },
          {
            id: 'default-v2',
            title: 'Claude → Codex → Antigravity',
            execution_mode: 'workflow',
            available: !!options.presetReady,
            errors: ['Permissões ainda indisponíveis'],
            default_for_ui: true,
            workflow: { definition },
            suggested_bindings: hints,
          },
          {
            id: 'openrouter-plan',
            title: 'OpenRouter',
            execution_mode: 'workflow',
            available: false,
            errors: ['Integração pendente'],
            blocked_by: ['V2-PROV-001'],
          },
        ])
      if (url === '/api/workflows' && init?.method === 'POST')
        return result(
          {
            id: 'wf-user',
            name: 'Meu workflow',
            read_only: false,
            latest_version: version('wv2', 2),
            suggested_bindings: hints,
          },
          201,
        )
      if (url === '/api/workflows')
        return result(
          options.customWorkflow || options.presetTrio
            ? [
                {
                  id: 'wf-user',
                  name: 'Meu workflow',
                  read_only: false,
                  latest_version: version('wv2', 2),
                },
              ]
            : [],
        )
      if (url === '/api/workflows/wf-user/versions')
        return result([version('wv1', 1), version('wv2', 2)])
      if (url === '/api/provider-configs' && options.presetTrio)
        return result(
          ['claude', 'codex', 'agy'].map((name) => ({
            id: `pc-${name}`,
            adapter: name,
            kind: 'agent_runtime',
            display_name: name,
            enabled: true,
            available: true,
            verified: true,
            model_selection: true,
            capabilities: ['text', 'planning', 'review', 'code_edit'],
            permission_modes: ['read_only', 'workspace_write'],
          })),
        )
      if (url === '/api/provider-configs')
        return result([
          {
            id: 'pc-local',
            adapter: 'fake',
            kind: 'agent_runtime',
            display_name: 'Runtime local',
            enabled: true,
            available: true,
            verified: true,
            model_selection: true,
            capabilities: ['text', 'planning', 'review', 'code_edit'],
            permission_modes: ['read_only', 'workspace_write'],
          },
        ])
      if (url.endsWith('/execution-config') && init?.method === 'POST') {
        const selection = JSON.parse(String(init.body)).workflow
        const implementation =
          selection.bindings[options.prototypeStep ? 'constructor' : 'impl']
        return result({
          ...config,
          configuration_digest: (implementation.model ? 'c' : 'b').repeat(64),
          configuration: {
            ...config.configuration,
            planner: 'fake',
            implementer: 'fake',
            reviewer: 'fake',
            planner_model: null,
            implementer_model: implementation.model,
          },
        })
      }
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
  it('supports valid stage IDs that match Object.prototype properties', async () => {
    const { fetcher } = setup({ customWorkflow: true, prototypeStep: true })
    await screen.findByText('configured-model', { exact: false })
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Workflow' }),
      'workflow:wf-user',
    )
    const model = await screen.findByRole('textbox', {
      name: 'Modelo para constructor',
    })
    expect(
      screen.getByRole('combobox', { name: 'Provider para constructor' }),
    ).toHaveValue('pc-local')
    await userEvent.type(model, 'selected-model')
    await waitFor(() => expect(screen.getByRole('checkbox')).toBeEnabled())
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(
      screen.getByRole('button', { name: 'Confirmar e iniciar' }),
    )
    await screen.findByRole('heading', { name: 'Acompanhamento da execução' })
    const write = fetcher.mock.calls.find(([url]) =>
      String(url).endsWith(`/requests/${task.id}/runs`),
    )!
    const body = JSON.parse(String(write[1]?.body))
    expect(Object.hasOwn(body.workflow.bindings, 'constructor')).toBe(true)
    expect(body.workflow.bindings.constructor.model).toBe('selected-model')
  })
  it('keeps the preset trio after the workflow list refresh loses suggestions', async () => {
    const { fetcher } = setup({ presetReady: true, presetTrio: true })
    await screen.findByRole('button', { name: 'Usar este preset' })
    await waitFor(() =>
      expect(
        screen.getByRole('combobox', { name: 'Provider para impl' }),
      ).toHaveValue('pc-codex'),
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Usar este preset' }),
    )
    await screen.findByRole('combobox', { name: 'Versão do workflow' })
    await waitFor(() => expect(screen.getByRole('checkbox')).toBeEnabled())
    expect(
      screen.getByRole('combobox', { name: 'Provider para plan' }),
    ).toHaveValue('pc-claude')
    expect(
      screen.getByRole('combobox', { name: 'Provider para impl' }),
    ).toHaveValue('pc-codex')
    expect(
      screen.getByRole('combobox', { name: 'Provider para review' }),
    ).toHaveValue('pc-agy')
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(
      screen.getByRole('button', { name: 'Confirmar e iniciar' }),
    )
    await screen.findByRole('heading', { name: 'Acompanhamento da execução' })
    const write = fetcher.mock.calls.find(([url]) =>
      String(url).endsWith(`/requests/${task.id}/runs`),
    )!
    const body = JSON.parse(String(write[1]?.body))
    expect([
      body.workflow.bindings.plan.provider_config_id,
      body.workflow.bindings.impl.provider_config_id,
      body.workflow.bindings.review.provider_config_id,
    ]).toEqual(['pc-claude', 'pc-codex', 'pc-agy'])
  })
  it('offers the new default when available and only clones on explicit selection', async () => {
    const { fetcher } = setup({ presetReady: true })
    await screen.findByRole('button', { name: 'Usar este preset' })
    expect(screen.getByRole('combobox', { name: 'Workflow' })).toHaveValue(
      'preset:default-v2',
    )
    expect(fetcher.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(
      false,
    )
    expect(
      screen.getByRole('button', { name: 'Confirmar e iniciar' }),
    ).toBeDisabled()
    await userEvent.click(
      screen.getByRole('button', { name: 'Usar este preset' }),
    )
    await screen.findByRole('textbox', { name: 'Modelo para impl' })
    await waitFor(() => expect(screen.getByRole('checkbox')).toBeEnabled())
    const writes = fetcher.mock.calls.filter(
      ([url, init]) => url === '/api/workflows' && init?.method === 'POST',
    )
    expect(writes).toHaveLength(1)
    expect(JSON.parse(String(writes[0][1]?.body))).toEqual({
      preset_id: 'default-v2',
    })
  })
  it('selects an immutable workflow version and models before confirmation', async () => {
    const { fetcher } = setup({ customWorkflow: true })
    await screen.findByText('configured-model', { exact: false })
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Workflow' }),
      'workflow:wf-user',
    )
    const model = await screen.findByRole('textbox', {
      name: 'Modelo para impl',
    })
    await userEvent.type(model, 'chosen-model')
    await waitFor(() => expect(screen.getByRole('checkbox')).toBeEnabled())
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(
      screen.getByRole('button', { name: 'Confirmar e iniciar' }),
    )
    await screen.findByRole('heading', { name: 'Acompanhamento da execução' })
    const posted = fetcher.mock.calls.find(([url]) =>
      String(url).endsWith(`/requests/${task.id}/runs`),
    )!
    const body = JSON.parse(String(posted[1]?.body))
    expect(body.workflow.workflow_version_id).toBe('wv2')
    expect(body.workflow.bindings.impl).toEqual({
      provider_config_id: 'pc-local',
      model: 'chosen-model',
      permission: 'workspace_write',
    })
    expect(body.configuration_digest).toBe('c'.repeat(64))
  })
  it('clears consent when changing a selected version or model', async () => {
    setup({ customWorkflow: true })
    await screen.findByText('configured-model', { exact: false })
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Workflow' }),
      'workflow:wf-user',
    )
    await screen.findByRole('textbox', { name: 'Modelo para impl' })
    await waitFor(() => expect(screen.getByRole('checkbox')).toBeEnabled())
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.selectOptions(
      await screen.findByRole('combobox', { name: 'Versão do workflow' }),
      'wv1',
    )
    expect(screen.getByRole('checkbox')).not.toBeChecked()
    await waitFor(() => expect(screen.getByRole('checkbox')).toBeEnabled())
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.type(
      screen.getByRole('textbox', { name: 'Modelo para impl' }),
      'changed',
    )
    expect(screen.getByRole('checkbox')).not.toBeChecked()
  })
  it('keeps unavailable presets disabled and explains the legacy default', async () => {
    setup()
    await screen.findByText('configured-model', { exact: false })
    expect(screen.getByRole('option', { name: /OpenRouter/ })).toBeDisabled()
    expect(screen.getByText(/padrão.*indisponível/i)).toBeInTheDocument()
  })
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
