import { test, expect } from '@playwright/test'

test('existing request starts the supervised workflow and preserves results after reload', async ({
  page,
  request,
}) => {
  test.skip(
    process.env.EXECUTION_E2E_MOCKED !== '1',
    'Only run against tests/fixtures/managed_server.py with mocked agents.',
  )
  const policy = await (await request.get('/api/project-policy')).json()
  expect(
    policy.roots.every((root: { path: string }) =>
      root.path.startsWith('/tmp/orchestrator-execution-qa.'),
    ),
  ).toBe(true)
  const projects = await (await request.get('/api/projects')).json()
  const project = projects.find(
    (value: { name: string }) => value.name === 'Task Manager API (test)',
  )
  expect(project).toBeTruthy()
  const before = await (
    await request.get(`/api/projects/${project.id}/requests`)
  ).json()
  await page.goto(`/projects/${project.id}`)
  await page
    .getByRole('button', { name: 'Iniciar execução', exact: true })
    .click()
  const dialog = page.getByRole('dialog', { name: 'Iniciar execução real' })
  await expect(dialog).toBeVisible()
  await expect(
    dialog.getByText('Task Manager API (test)', { exact: true }),
  ).toBeVisible()
  await expect(
    dialog
      .getByText('Criar uma API REST para gerenciar tarefas pessoais.', {
        exact: true,
      })
      .first(),
  ).toBeVisible()
  await expect(dialog.getByRole('checkbox')).toBeEnabled()
  await expect(
    dialog.getByRole('button', { name: 'Confirmar e iniciar' }),
  ).toBeDisabled()
  await dialog.getByRole('checkbox').check()
  await dialog.getByRole('button', { name: 'Confirmar e iniciar' }).click()
  await expect(page).toHaveURL(/\/executions\/run-/)
  await expect(
    page.getByRole('heading', {
      name: 'Criar uma API REST para gerenciar tarefas pessoais.',
    }),
  ).toBeVisible()
  await expect(page.locator('.execution-summary .status')).toHaveText(
    'Revisão humana',
    { timeout: 30000 },
  )
  await expect(
    page
      .getByRole('tabpanel', { name: 'Timeline' })
      .getByText('Workflow finalizado', { exact: true }),
  ).toBeVisible()
  await page.reload()
  await expect(page.locator('.execution-summary .status')).toHaveText(
    'Revisão humana',
  )
  await page
    .getByRole('tab', { name: 'Testes e revisões', exact: true })
    .click()
  await expect(
    page.getByText('Revisão automática aprovada', { exact: true }),
  ).toBeVisible()
  await page.getByText('Saída completa registrada dos testes').click()
  await expect(page.locator('.test-output pre')).toContainText('1 passed in')
  const after = await (
    await request.get(`/api/projects/${project.id}/requests`)
  ).json()
  expect(after.map((value: { id: string }) => value.id)).toEqual(
    before.map((value: { id: string }) => value.id),
  )
  const linked = await (
    await request.get(`/api/projects/${project.id}/runs?linked_only=true`)
  ).json()
  expect(linked[0].request_id).toBe(before[0].id)
})
