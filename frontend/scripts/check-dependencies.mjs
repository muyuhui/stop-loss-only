import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

export function findDependencyProblems(packageJson, packageLock, getInstalledVersion) {
  const directDependencies = new Set([
    ...Object.keys(packageJson.dependencies ?? {}),
    ...Object.keys(packageJson.devDependencies ?? {}),
  ])
  const lockedPackages = packageLock.packages ?? {}
  const problems = []

  for (const name of [...directDependencies].sort()) {
    const locked = lockedPackages[`node_modules/${name}`]
    if (!locked?.version) {
      problems.push(`${name}: package-lock.json 中缺少直接依赖的锁定版本`)
      continue
    }

    const installedVersion = getInstalledVersion(name)
    if (!installedVersion) {
      problems.push(`${name}: 未安装（锁定版本 ${locked.version}）`)
    } else if (installedVersion !== locked.version) {
      problems.push(`${name}: 已安装 ${installedVersion}，锁定版本为 ${locked.version}`)
    }
  }

  return problems
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

export function checkInstalledDependencies(frontendRoot) {
  const packageJson = readJson(path.join(frontendRoot, 'package.json'))
  const packageLock = readJson(path.join(frontendRoot, 'package-lock.json'))
  const getInstalledVersion = (name) => {
    const installedManifest = path.join(frontendRoot, 'node_modules', name, 'package.json')
    try {
      return readJson(installedManifest).version
    } catch (error) {
      if (error.code === 'ENOENT') return undefined
      throw error
    }
  }

  return {
    dependencyCount: new Set([
      ...Object.keys(packageJson.dependencies ?? {}),
      ...Object.keys(packageJson.devDependencies ?? {}),
    ]).size,
    problems: findDependencyProblems(packageJson, packageLock, getInstalledVersion),
  }
}

function run() {
  const frontendRoot = fileURLToPath(new URL('..', import.meta.url))
  try {
    const { dependencyCount, problems } = checkInstalledDependencies(frontendRoot)
    if (problems.length > 0) {
      console.error('前端依赖预检失败：')
      for (const problem of problems) console.error(`- ${problem}`)
      process.exitCode = 1
      return
    }
    console.log(`前端依赖预检通过（${dependencyCount} 个直接依赖）。`)
  } catch (error) {
    console.error(`前端依赖预检失败：${error.message}`)
    process.exitCode = 1
  }
}

const invokedPath = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : undefined
if (invokedPath === import.meta.url) run()
