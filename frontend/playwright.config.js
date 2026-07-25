import { defineConfig } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const backendPort = 18101
const frontendPort = 14173
const runRoot = resolve('../.tmp', `playwright-${process.pid}-${Date.now()}`)
mkdirSync(runRoot, { recursive: true })

export default defineConfig({
  testDir: './tests/e2e',
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
  webServer: [
    {
      command: 'python ../scripts/e2e_backend.py',
      cwd: '.',
      url: `http://127.0.0.1:${backendPort}/api/health/ready`,
      timeout: 30_000,
      reuseExistingServer: false,
      env: {
        STOP_LOSS_DATABASE_URL: `sqlite:///${resolve(runRoot, 'e2e.db').replaceAll('\\', '/')}`,
        STOP_LOSS_BACKEND_PORT: String(backendPort),
        STOP_LOSS_SCHEDULER_ENABLED: '0',
        STOP_LOSS_FIXTURE_PRICE: '8.8',
        STOP_LOSS_NETWORK_SENTINEL: '1',
        STOP_LOSS_NETWORK_ALLOW_LOOPBACK: '1',
        STOP_LOSS_TEMP_DIR: runRoot,
        STOP_LOSS_LOG_FORMAT: 'text',
      },
    },
    {
      command: `npm run preview -- --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      cwd: '.',
      url: `http://127.0.0.1:${frontendPort}`,
      timeout: 30_000,
      reuseExistingServer: false,
      env: { VITE_API_PROXY_TARGET: `http://127.0.0.1:${backendPort}` },
    },
  ],
})
