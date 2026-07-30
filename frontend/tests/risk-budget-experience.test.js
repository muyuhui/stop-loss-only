import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const base = new URL('../src/', import.meta.url)

test('risk budget views preserve unavailable and indeterminate semantics', async () => {
  const [dashboard, settings, planner] = await Promise.all([
    readFile(fileURLToPath(new URL('views/Dashboard.vue', base)), 'utf8'),
    readFile(fileURLToPath(new URL('views/Settings.vue', base)), 'utf8'),
    readFile(fileURLToPath(new URL('views/RiskPlanner.vue', base)), 'utf8'),
  ])
  assert.match(dashboard, /remaining_capacity === null/)
  assert.match(dashboard, /未知值不会显示为零/)
  assert.match(settings, /账户权益由你手工维护/)
  assert.match(planner, /所有财务计算均由后端 Decimal 引擎完成/)
  assert.match(planner, /系统不知道你的券商可用现金/)
  assert.match(planner, /风险约束下的最大数量/)
  assert.doesNotMatch(planner, /推荐买入/)
})

test('planner is keyboard-labelled and mobile-safe', async () => {
  const planner = await readFile(fileURLToPath(new URL('views/RiskPlanner.vue', base)), 'utf8')
  assert.match(planner, /@submit\.prevent="preview"/)
  assert.match(planner, /aria-label="计划买入价"/)
  assert.match(planner, /aria-live="polite"/)
  assert.match(planner, /@media \(max-width: 767px\)/)
  assert.match(planner, /min-height:\s*44px/)
})

test('planner numeric steps match their displayed decimal precision', async () => {
  const planner = await readFile(fileURLToPath(new URL('views/RiskPlanner.vue', base)), 'utf8')
  assert.match(planner, /label="计划买入价"[^\n]*:step="0\.0001"/)
  assert.match(planner, /label="预计买入费用"[^\n]*:step="0\.01"/)
  assert.match(planner, /label="单笔风险比例（可选）"[^\n]*:step="0\.01"/)
})

test('mobile navigation exposes the planner without overflow-prone fixed widths', async () => {
  const [app, styles] = await Promise.all([
    readFile(fileURLToPath(new URL('App.vue', base)), 'utf8'),
    readFile(fileURLToPath(new URL('styles.css', base)), 'utf8'),
  ])
  assert.match(app, /path: '\/planner'/)
  assert.match(app, /desktopLabel: '风险试算'/)
  assert.match(styles, /grid-template-columns:\s*repeat\(5,\s*minmax\(0,\s*1fr\)\)/)
})
