import { test, expect } from '@playwright/test'
// Read-only smoke tests against a running API and its existing SQLite database.
// No fixtures are written to the real event store.
test('real data, execution navigation, agent monitor and settings', async ({
  page,
  request,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const response = await request.get('/api/overview')
  expect(response.ok()).toBeTruthy()
  const overview = await response.json()
  await page.goto('/overview')
  await expect(page.getByText('API conectada')).toBeVisible()
  await expect(
    page.getByRole('heading', { name: 'Execuções recentes' }),
  ).toBeVisible()
  await expect(page.locator('.metric').first().locator('strong')).toHaveText(
    String(overview.total),
  )
  await page.screenshot({
    path: '/tmp/orchestrator-desktop.png',
    fullPage: true,
  })
  await page
    .getByRole('navigation')
    .getByRole('link', { name: 'Executions' })
    .click()
  if (overview.total > 0) {
    await page.locator('.run-link').first().click()
    await expect(
      page.getByRole('heading', { name: 'Timeline de eventos' }),
    ).toBeVisible()
    await page.locator('.timeline-event summary').first().click()
    await expect(
      page.locator('.timeline-event').first().locator('.event-content'),
    ).toBeVisible()
    await page.getByRole('tab', { name: 'Agentes', exact: true }).click()
    await expect(
      page.getByRole('heading', { name: 'Planner', exact: true }),
    ).toBeVisible()
    await page
      .getByRole('tab', { name: 'Testes e revisões', exact: true })
      .click()
    await expect(
      page.getByRole('heading', { name: 'Testes e revisões', exact: true }),
    ).toBeVisible()
    await page.reload()
    await expect(
      page.getByRole('heading', { name: 'Testes e revisões', exact: true }),
    ).toBeVisible()
  }
  await page
    .getByRole('navigation')
    .getByRole('link', { name: 'Settings' })
    .click()
  await expect(
    page.getByRole('heading', { name: 'Agentes e ambiente' }),
  ).toBeVisible()
  expect(errors).toEqual([])
})
for (const width of [390, 768]) {
  test(`responsive navigation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    await page.goto('/overview')
    await expect(
      page.getByRole('heading', { name: 'Execuções recentes' }),
    ).toBeVisible()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true)
    await page.screenshot({
      path: `/tmp/orchestrator-${width}.png`,
      fullPage: true,
    })
    if (width < 700)
      await page.getByRole('button', { name: 'Abrir navegação' }).click()
    await page
      .getByRole('navigation')
      .getByRole('link', { name: 'Executions' })
      .click()
    await expect(
      page.getByRole('heading', { name: 'Executions.' }),
    ).toBeVisible()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true)
  })
}
