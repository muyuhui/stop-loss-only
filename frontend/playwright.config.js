import { defineConfig } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const backendPort = 18101
const frontendPort = 14173
const runRoot = resolve('../.tmp', `playwright-${process.pid}-${Date.now()}`)
mkdirSync(runRoot, { recursive: true })
process.env.STOP_LOSS_E2E_RUN_ROOT = runRoot
process.env.STOP_LOSS_E2E_BACKEND_PORT = String(backendPort)
process.env.STOP_LOSS_E2E_FRONTEND_PORT = String(frontendPort)

export default defineConfig({
  testDir: './tests/e2e',
  globalSetup: './tests/e2e/global-setup.js',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  reporter: [['line']],
  outputDir: resolve(runRoot, 'artifacts'),
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'mobile-390', use: { viewport: { width: 390, height: 844 } } },
    { name: 'tablet-768', use: { viewport: { width: 768, height: 1024 } } },
    { name: 'desktop-1440', use: { viewport: { width: 1440, height: 900 } } },
  ],
})
