import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: process.env.DASHBOARD_URL ?? 'http://127.0.0.1:5173',
    headless: true,
    launchOptions: {
      executablePath: process.env.CHROME_PATH ?? '/usr/bin/google-chrome',
      args: ['--no-sandbox'],
    },
  },
})
