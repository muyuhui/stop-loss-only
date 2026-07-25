import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  checkInstalledDependencies,
  findDependencyProblems,
} from '../scripts/check-dependencies.mjs'

const packageJson = {
  dependencies: { vue: '^3.5.0' },
  devDependencies: { vite: '^8.0.0' },
}

const packageLock = {
  packages: {
    'node_modules/vue': { version: '3.5.40' },
    'node_modules/vite': { version: '8.1.5' },
  },
}

test('dependency check accepts direct dependencies installed at locked versions', () => {
  const installedVersions = new Map([
    ['vue', '3.5.40'],
    ['vite', '8.1.5'],
  ])

  assert.deepEqual(
    findDependencyProblems(packageJson, packageLock, (name) => installedVersions.get(name)),
    [],
  )
})

test('dependency check reports a missing direct dependency', () => {
  const problems = findDependencyProblems(packageJson, packageLock, (name) =>
    name === 'vue' ? '3.5.40' : undefined,
  )

  assert.equal(problems.length, 1)
  assert.match(problems[0], /vite/)
  assert.match(problems[0], /未安装/)
})

test('dependency check reports an installed version that differs from package-lock', () => {
  const problems = findDependencyProblems(packageJson, packageLock, () => '0.0.1')

  assert.equal(problems.length, 2)
  assert.match(problems[0], /锁定版本/)
  assert.match(problems[0], /0\.0\.1/)
})

test('dependency check reports a direct dependency missing from package-lock', () => {
  const incompleteLock = { packages: { 'node_modules/vue': { version: '3.5.40' } } }
  const problems = findDependencyProblems(packageJson, incompleteLock, () => '3.5.40')

  assert.equal(problems.length, 1)
  assert.match(problems[0], /vite/)
  assert.match(problems[0], /package-lock\.json/)
})

test('current frontend installation matches package-lock', () => {
  const frontendRoot = fileURLToPath(new URL('..', import.meta.url))
  const result = checkInstalledDependencies(frontendRoot)

  assert.ok(result.dependencyCount > 0)
  assert.deepEqual(result.problems, [])
})

test('dependency check CLI succeeds for the current frontend installation', () => {
  const script = fileURLToPath(new URL('../scripts/check-dependencies.mjs', import.meta.url))
  const result = spawnSync(process.execPath, [script], { encoding: 'utf8' })

  assert.equal(result.status, 0, result.stderr)
  assert.match(result.stdout, /\d+ 个直接依赖/)
})
