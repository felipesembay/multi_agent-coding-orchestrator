import { test as base, expect } from '@playwright/test'

// APIRequestContext reads follow the same token bootstrap as the browser UI.
export const test = base.extend({
  request: async ({ playwright, baseURL }, provide) => {
    const bootstrap = await playwright.request.newContext({ baseURL })
    let token: string
    try {
      const response = await bootstrap.get('/api/session')
      if (!response.ok()) throw new Error('Local session bootstrap failed')
      const data: unknown = await response.json()
      if (
        !data ||
        typeof data !== 'object' ||
        !('csrf_token' in data) ||
        typeof data.csrf_token !== 'string' ||
        !data.csrf_token
      )
        throw new Error('Invalid local session response')
      token = data.csrf_token
    } finally {
      await bootstrap.dispose()
    }
    const authenticated = await playwright.request.newContext({
      baseURL,
      extraHTTPHeaders: { 'X-Orchestrator-CSRF': token },
    })
    try {
      await provide(authenticated)
    } finally {
      await authenticated.dispose()
    }
  },
})
export { expect }
