import fs from 'node:fs'
import path from 'node:path'

const dist = path.resolve('dist')
const manifest = JSON.parse(fs.readFileSync(path.join(dist, '.vite', 'manifest.json'), 'utf8'))
const ENTRY_BUDGET = 500 * 1024
const CHUNK_BUDGET = 400 * 1024
let failed = false

for (const item of Object.values(manifest)) {
  if (!item.file?.endsWith('.js')) continue
  const bytes = fs.statSync(path.join(dist, item.file)).size
  const budget = item.isEntry ? ENTRY_BUDGET : CHUNK_BUDGET
  console.log(`${item.isEntry ? 'entry' : 'chunk'} ${item.file}: ${bytes} / ${budget} bytes`)
  if (bytes > budget) failed = true
}
if (failed) process.exit(1)
