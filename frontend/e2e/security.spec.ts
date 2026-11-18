import { test, expect } from './fixtures'

test('browser authenticates reads while raw API requests stay protected', async ({
  page,
  playwright,
  baseURL,
  request,
}) => {
  const anonymous = await playwright.request.newContext({ baseURL })
  try {
    expect((await anonymous.get('/api/health')).status()).toBe(200)
    expect((await anonymous.get('/api/session')).status()).toBe(200)
    for (const path of ['/runs', '/overview', '/settings', '/providers'])
      expect((await anonymous.get(`/api${path}`)).status()).toBe(403)
    expect(
      (
        await anonymous.get('/api/runs', { headers: { Host: 'evil.example' } })
      ).status(),
    ).toBe(403)
    expect((await request.get('/api/overview')).status()).toBe(200)
  } finally {
    await anonymous.dispose()
  }
  const statuses: number[] = []
  page.on('response', (response) => {
    if (response.url().endsWith('/api/settings'))
      statuses.push(response.status())
  })
  await page.goto('/settings')
  await expect(
    page.getByRole('heading', { name: 'Agentes e ambiente' }),
  ).toBeVisible()
  expect(statuses).toContain(200)
  expect(statuses).not.toContain(403)
  await page.reload()
  await expect(
    page.getByRole('heading', { name: 'Agentes e ambiente' }),
  ).toBeVisible()
  expect(
    await page.evaluate(() =>
      [...Object.keys(localStorage), ...Object.keys(sessionStorage)].some(
        (key) => /token|csrf|bearer/i.test(key),
      ),
    ),
  ).toBe(false)
})
