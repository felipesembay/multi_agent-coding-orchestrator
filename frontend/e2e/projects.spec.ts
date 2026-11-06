import { test, expect } from '@playwright/test'

for (const width of [390, 768, 1440]) {
  test(`project pages fit the workspace at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/')
    await expect(
      page.getByRole('heading', { name: 'Seus projetos.' }),
    ).toBeVisible()
    await expect(
      page.getByRole('link', { name: 'Novo projeto', exact: true }),
    ).toBeVisible()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
    await page.screenshot({
      path: `/tmp/orchestrator-projects-${width}.png`,
      fullPage: true,
    })
    await page.getByRole('link', { name: 'Novo projeto', exact: true }).click()
    await expect(
      page.getByRole('heading', { name: 'Um espaço para construir.' }),
    ).toBeVisible()
    await expect(
      page.getByRole('heading', { name: 'Diretórios autorizados' }),
    ).toBeVisible()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
    await page.screenshot({
      path: `/tmp/orchestrator-project-form-${width}.png`,
      fullPage: true,
    })
  })
}

test('create, confirm, persist requirements, edit, archive and reconnect a repository', async ({
  page,
  request,
}) => {
  test.skip(
    process.env.PROJECTS_E2E_WRITE !== '1',
    'Writes require an explicitly configured temporary test database.',
  )
  const policy = await (await request.get('/api/project-policy')).json()
  const root = policy.roots.find(
    (value: { path: string; available: boolean }) =>
      value.available &&
      value.path.startsWith('/tmp/orchestrator-projects-qa.'),
  )
  expect(
    root,
    'Use only an isolated /tmp/orchestrator-projects-qa.* root',
  ).toBeTruthy()
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const suffix = Date.now()
  const name = `Sistema de Recomendação de Filmes ${suffix}`
  const path = `${root.path}/filmes-${suffix}`
  await page.goto('/projects/new')
  await page.getByRole('radio', { name: /Criar projeto novo/ }).check()
  await page
    .getByRole('textbox', { name: 'Nome do projeto', exact: true })
    .fill(name)
  await page
    .getByRole('textbox', { name: 'Descrição', exact: true })
    .fill('Plataforma local de recomendação de filmes')
  await page
    .getByRole('textbox', { name: 'Objetivos', exact: true })
    .fill('API FastAPI com PostgreSQL, testes e documentação')
  await page.getByRole('textbox', { name: /Caminho absoluto/ }).fill(path)
  await page.getByRole('button', { name: 'Revisar projeto' }).click()
  await expect(
    page.getByRole('heading', { name: 'Revise antes de confirmar' }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Confirmar e criar projeto' }),
  ).toBeDisabled()
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: 'Confirmar e criar projeto' }).click()
  await expect(
    page.getByRole('heading', { name: 'O que vamos desenvolver?' }),
  ).toBeVisible()
  const workspace = page.url()
  await page
    .getByRole('textbox', { name: 'Título da solicitação' })
    .fill('Criar a API de recomendações')
  await page
    .getByRole('textbox', {
      name: 'Requisitos em linguagem natural',
      exact: true,
    })
    .fill(
      'Crie uma API FastAPI para recomendar filmes, com PostgreSQL, testes automatizados e documentação.',
    )
  await page.getByRole('button', { name: 'Salvar solicitação' }).click()
  await expect(
    page.getByText('Criar a API de recomendações', { exact: true }),
  ).toBeVisible()
  await page.reload()
  await expect(
    page.getByText('Criar a API de recomendações', { exact: true }),
  ).toBeVisible()
  await page.getByText('Criar a API de recomendações', { exact: true }).click()
  await expect(page.locator('.project-request-item p')).toContainText(
    'PostgreSQL',
  )
  await page.evaluate(() => scrollTo(0, 0))
  await page.screenshot({
    path: '/tmp/orchestrator-project-workspace.png',
    fullPage: true,
  })
  await page
    .getByRole('button', { name: 'Editar projeto', exact: true })
    .click()
  await page
    .getByRole('textbox', { name: 'Nome do projeto', exact: true })
    .fill(`${name} v2`)
  await page
    .getByRole('combobox', { name: 'Estado', exact: true })
    .selectOption('archived')
  await page.getByRole('button', { name: 'Salvar alterações' }).click()
  await expect(
    page.getByRole('button', { name: 'Salvar solicitação' }),
  ).toBeDisabled()
  await page.reload()
  await expect(page.getByRole('heading', { name: `${name} v2.` })).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Salvar solicitação' }),
  ).toBeDisabled()
  await page
    .getByRole('button', { name: 'Editar projeto', exact: true })
    .click()
  await page
    .getByRole('combobox', { name: 'Estado', exact: true })
    .selectOption('active')
  await page.getByRole('button', { name: 'Salvar alterações' }).click()
  await expect(
    page.getByRole('button', { name: 'Salvar solicitação' }),
  ).toBeEnabled()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
  await page.screenshot({
    path: '/tmp/orchestrator-project-workspace-mobile.png',
    fullPage: true,
  })
  await page.goto('/projects/new')
  await page
    .getByRole('textbox', { name: 'Nome do projeto', exact: true })
    .fill(`Repositório associado ${suffix}`)
  await page.getByRole('textbox', { name: /Caminho absoluto/ }).fill(path)
  await page.getByRole('button', { name: 'Revisar projeto' }).click()
  await expect(
    page.getByRole('heading', { name: 'Revise antes de confirmar' }),
  ).toBeVisible()
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: 'Confirmar e criar projeto' }).click()
  await expect(
    page.getByRole('heading', { name: 'O que vamos desenvolver?' }),
  ).toBeVisible()
  await page.goto(workspace)
  await expect(
    page.getByText('Criar a API de recomendações', { exact: true }),
  ).toBeVisible()
  expect(errors).toEqual([])
})
