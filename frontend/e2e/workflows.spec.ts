import { test, expect } from './fixtures'

test.beforeEach(async ({ request }) => {
  test.skip(
    process.env.EXECUTION_E2E_MOCKED !== '1',
    'Requires isolated QA API with mocked agents.',
  )
  const policy = await (await request.get('/api/project-policy')).json()
  expect(policy.roots.length).toBeGreaterThan(0)
  expect(
    policy.roots.every((root: { path: string }) =>
      root.path.startsWith('/tmp/orchestrator-execution-qa.'),
    ),
  ).toBe(true)
})

test('workflow editor creates and versions definitions without starting a run', async ({
  page,
  request,
}) => {
  let starts = 0
  page.on('request', (req) => {
    if (req.method() === 'POST' && /\/runs(?:\?|$)/.test(req.url())) starts++
  })
  await page.goto('/workflows')
  await page.getByRole('link', { name: 'Novo workflow', exact: true }).click()
  await page.getByRole('textbox', { name: 'Nome do workflow' }).fill('Fluxo QA')
  await page.getByRole('button', { name: 'Adicionar etapa' }).click()
  await expect(page.getByText('document-1', { exact: true })).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Mover document-1 para cima' }),
  ).toBeDisabled()
  await page.getByRole('button', { name: 'Mover review para cima' }).click()
  await page.getByRole('button', { name: 'Mover review para baixo' }).click()
  await page.getByRole('spinbutton', { name: 'Tentativas para impl' }).fill('0')
  await expect(page.getByRole('alert')).toContainText('Tentativas')
  await expect(
    page.getByRole('button', { name: 'Salvar workflow', exact: true }),
  ).toBeDisabled()
  await page.getByRole('spinbutton', { name: 'Tentativas para impl' }).fill('3')
  await page
    .getByRole('button', { name: 'Salvar workflow', exact: true })
    .click()
  await expect(page).toHaveURL(/\/workflows\/wf-.*\?version=/)
  const workflowId = new URL(page.url()).pathname.split('/').at(-1)
  const endpoint = `/api/workflows/${workflowId}/versions`
  const original = await (await request.get(endpoint)).json()
  expect(original).toHaveLength(1)
  await page
    .getByRole('textbox', { name: 'Nome do workflow' })
    .fill('Fluxo QA revisado')
  await page.getByRole('button', { name: 'Salvar nova versão' }).click()
  await expect(
    page.getByRole('combobox', { name: 'Versão do workflow' }),
  ).toHaveValue(/.+/)
  await expect
    .poll(async () => (await (await request.get(endpoint)).json()).length)
    .toBe(2)
  const versions = await (await request.get(endpoint)).json()
  expect(versions[0]).toEqual(original[0])
  expect(versions[1].definition.name).toBe('Fluxo QA revisado')
  await page.reload()
  await expect(
    page.getByRole('textbox', { name: 'Nome do workflow' }),
  ).toHaveValue('Fluxo QA revisado')
  await page
    .getByRole('combobox', { name: 'Versão do workflow' })
    .selectOption(original[0].id)
  await expect(
    page.getByRole('textbox', { name: 'Nome do workflow' }),
  ).toHaveValue('Fluxo QA')
  expect(starts).toBe(0)
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(
    page.getByRole('button', { name: 'Criar cópia', exact: true }),
  ).toBeVisible()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
})

test('system preset is cloned into an editable definition with execution restrictions intact', async ({
  page,
  request,
}) => {
  const before = await (await request.get('/api/workflow-presets')).json()
  await page.goto('/workflows')
  await expect(
    page.getByRole('button', { name: 'Criar cópia de openrouter-plan' }),
  ).toBeDisabled()
  await page.getByRole('button', { name: 'Criar cópia de default-v2' }).click()
  await expect(page).toHaveURL(/\/workflows\/wf-.*\?version=/)
  await expect(
    page.getByRole('textbox', { name: 'Nome do workflow' }),
  ).toBeEnabled()
  await expect(
    page.getByRole('textbox', { name: 'Nome do workflow' }),
  ).toHaveValue('default-v2 (cópia)')
  const after = await (await request.get('/api/workflow-presets')).json()
  expect(after).toEqual(before)
  expect(
    after.find((p: { id: string }) => p.id === 'openrouter-plan').available,
  ).toBe(false)
})
