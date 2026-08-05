import { spawn } from 'node:child_process'
import { resolve } from 'node:path'

const wait = (milliseconds) => new Promise(resolveWait => setTimeout(resolveWait, milliseconds))

async function waitForUrl(url, child, timeout = 30_000) {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(`E2E server exited before becoming ready: ${url}`)
    }
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      // Server startup is still in progress.
    }
    await wait(100)
  }
  throw new Error(`E2E server did not become ready within ${timeout}ms: ${url}`)
}

async function stopChild(child) {
  if (!child || child.exitCode !== null) return
  const exited = new Promise(resolveExit => child.once('exit', resolveExit))
  child.kill('SIGTERM')
  await Promise.race([exited, wait(5_000)])
  if (child.exitCode === null) {
    child.kill('SIGKILL')
    await exited
  }
}

export default async function globalSetup() {
  const runRoot = process.env.STOP_LOSS_E2E_RUN_ROOT
  const backendPort = process.env.STOP_LOSS_E2E_BACKEND_PORT
  const frontendPort = process.env.STOP_LOSS_E2E_FRONTEND_PORT
  if (!runRoot || !backendPort || !frontendPort) {
    throw new Error('E2E runtime paths and ports were not configured')
  }

  const backend = spawn(
    process.env.PYTHON || 'python',
    [resolve('../scripts/e2e_backend.py')],
    {
      cwd: resolve('.'),
      shell: false,
      windowsHide: true,
      stdio: 'inherit',
      env: {
        ...process.env,
        STOP_LOSS_DATABASE_URL: `sqlite:///${resolve(runRoot, 'e2e.db').replaceAll('\\', '/')}`,
        STOP_LOSS_DESKTOP_NOTIFY_FIXTURE: '1',
        STOP_LOSS_DESKTOP_NOTIFY_PATH: resolve(runRoot, 'desktop-notify.jsonl'),
        STOP_LOSS_BACKEND_PORT: backendPort,
        STOP_LOSS_SCHEDULER_ENABLED: '0',
        STOP_LOSS_FIXTURE_PRICE: '8.8',
        STOP_LOSS_FIXTURE_HISTORY_POINTS: '60',
        STOP_LOSS_DEEPSEEK_FIXTURE: '1',
        STOP_LOSS_NETWORK_SENTINEL: '1',
        STOP_LOSS_NETWORK_ALLOW_LOOPBACK: '1',
        STOP_LOSS_TEMP_DIR: runRoot,
        STOP_LOSS_LOG_FORMAT: 'text',
      },
    },
  )
  const frontend = spawn(
    process.execPath,
    [
      resolve('node_modules/vite/bin/vite.js'),
      'preview',
      '--host', '127.0.0.1',
      '--port', frontendPort,
      '--strictPort',
    ],
    {
      cwd: resolve('.'),
      shell: false,
      windowsHide: true,
      stdio: 'inherit',
      env: {
        ...process.env,
        VITE_API_PROXY_TARGET: `http://127.0.0.1:${backendPort}`,
      },
    },
  )

  try {
    await Promise.all([
      waitForUrl(`http://127.0.0.1:${backendPort}/api/health/ready`, backend),
      waitForUrl(`http://127.0.0.1:${frontendPort}`, frontend),
    ])
  } catch (error) {
    await Promise.all([stopChild(frontend), stopChild(backend)])
    throw error
  }

  return async () => {
    await Promise.all([stopChild(frontend), stopChild(backend)])
  }
}
