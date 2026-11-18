import { test, expect } from './fixtures'

test('light and dark themes persist across routes and reloads on desktop and mobile', async ({
  page,
}) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Ativar tema claro' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await page.reload()
  await expect(
    page.getByRole('button', { name: 'Ativar tema escuro' }),
  ).toBeVisible()
  const background = await page
    .locator('html')
    .evaluate((element) => getComputedStyle(element).backgroundColor)
  const lightChannels = background.match(/\d+/g)!.slice(0, 3).map(Number)
  expect(Math.min(...lightChannels)).toBeGreaterThan(220)
  for (const path of [
    '/',
    '/projects/new',
    '/overview',
    '/executions',
    '/agents',
    '/reviews',
    '/settings',
  ]) {
    await page.goto(path)
    await expect(
      page.getByRole('button', { name: 'Ativar tema escuro' }),
    ).toBeVisible()
    expect(await page.locator('html').getAttribute('data-theme')).toBe('light')
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
  }
  await page.goto('/')
  await page.screenshot({ path: '/tmp/orchestrator-light.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(
    page.getByRole('button', { name: 'Ativar tema escuro' }),
  ).toBeVisible()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
  await page.getByRole('button', { name: 'Ativar tema escuro' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.reload()
  await expect(
    page.getByRole('button', { name: 'Ativar tema claro' }),
  ).toBeVisible()
})

test('failed project can be removed while execution evidence and repository remain', async ({
  page,
  request,
}) => {
  test.skip(
    process.env.UI_E2E_WRITE !== '1',
    'Writes require the dedicated temporary UI database.',
  )
  const policy = await (await request.get('/api/project-policy')).json()
  expect(policy.roots.length).toBeGreaterThan(0)
  expect(
    policy.roots.every((value: { path: string }) =>
      value.path.startsWith('/tmp/orchestrator-ui-qa.'),
    ),
  ).toBe(true)
  const projects = await (await request.get('/api/projects')).json()
  const project = projects.find(
    (value: { name: string }) => value.name === 'Projeto com falha (QA)',
  )
  expect(project).toBeTruthy()
  const runs = await (
    await request.get(`/api/projects/${project.id}/runs?linked_only=true`)
  ).json()
  expect(runs[0].status).toBe('failed')
  await page.goto(`/projects/${project.id}`)
  await page.getByRole('button', { name: 'Ativar tema claro' }).click()
  await page
    .getByRole('button', { name: 'Excluir projeto', exact: true })
    .click()
  const dialog = page.getByRole('dialog', { name: 'Excluir projeto?' })
  await expect(dialog).toBeVisible()
  await expect(
    dialog.getByRole('button', { name: 'Confirmar exclusão' }),
  ).toBeDisabled()
  await dialog
    .getByRole('textbox', { name: 'Digite o nome do projeto para confirmar' })
    .fill(project.name)
  await page.screenshot({ path: '/tmp/orchestrator-delete-light.png' })
  await dialog.getByRole('button', { name: 'Confirmar exclusão' }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(
    page
      .getByRole('status')
      .filter({ hasText: 'Projeto excluído da interface' }),
  ).toBeVisible()
  await expect(
    page.getByRole('link', { name: /Projeto com falha \(QA\)/ }),
  ).toHaveCount(0)
  await page.reload()
  expect((await request.get(`/api/projects/${project.id}`)).status()).toBe(404)
  const preserved = await (
    await request.get(`/api/runs/${runs[0].run_id}`)
  ).json()
  expect(preserved.project_deleted).toBe(true)
  expect(preserved.events.length).toBeGreaterThan(0)
  await page.goto(`/executions/${runs[0].run_id}`)
  await expect(
    page.getByText('Este projeto foi excluído do cadastro.', { exact: false }),
  ).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Todas as execuções', exact: true }),
  ).toBeVisible()
})
