import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

import { dashboardRiskSummary, sortHoldingsByRisk } from '../src/utils/dashboard.js'
import { holdingPayload, priceInputMeta, stopLossInputMeta } from '../src/utils/holdingForm.js'
import { detectSettingsPreset, settingsForPreset } from '../src/utils/settingsPresets.js'

test('dashboard orders triggered and nearest stop-loss holdings first', () => {
  const items = [
    { id: 1, status: 'holding', stop_loss_distance_pct: 12 },
    { id: 2, status: 'holding', stop_loss_distance_pct: 2 },
    { id: 3, status: 'triggered', stop_loss_distance_pct: -1 },
  ]
  assert.deepEqual(sortHoldingsByRisk(items).map(item => item.id), [3, 2, 1])
  assert.match(dashboardRiskSummary({ triggered_count: 1, holdings: items }).title, /已触发止损/)
  assert.match(dashboardRiskSummary({ triggered_count: 0, holdings: items.slice(0, 2) }).title, /非常接近止损/)
})

test('holding form metadata and payload follow the selected stop-loss method', () => {
  assert.deepEqual(priceInputMeta('stock'), { precision: 2, step: 0.01, min: 0.01 })
  assert.deepEqual(priceInputMeta('fund'), { precision: 3, step: 0.001, min: 0.001 })
  assert.deepEqual(stopLossInputMeta('fixed', 'stock'), { unit: '元', precision: 2, step: 0.01, min: 0.01, help: '达到这个价格时触发止损，例如 9.00。' })
  assert.equal(stopLossInputMeta('fixed', 'fund').precision, 3)
  assert.equal(stopLossInputMeta('trailing').unit, '%')
  assert.deepEqual(holdingPayload({ code: ' 000001 ', name: ' 平安银行 ', buy_price: '10.5', quantity: '100', stop_loss_value: '8', type: 'stock' }), {
    code: '000001', name: '平安银行', buy_price: 10.5, quantity: 100, stop_loss_value: 8, type: 'stock',
  })
})

test('settings presets map to the existing runtime fields and detect custom values', () => {
  assert.deepEqual(settingsForPreset('timely'), { pollInterval: 10, monitorInterval: 1 })
  assert.deepEqual(settingsForPreset('balanced'), { pollInterval: 30, monitorInterval: 5 })
  assert.deepEqual(settingsForPreset('efficient'), { pollInterval: 60, monitorInterval: 15 })
  assert.equal(detectSettingsPreset(30, 5), 'balanced')
  assert.equal(detectSettingsPreset(45, 7), 'custom')
})

test('application shell exposes named navigation and responsive overflow rules', async () => {
  const base = new URL('../src/', import.meta.url)
  const [app, styles] = await Promise.all([
    readFile(fileURLToPath(new URL('App.vue', base)), 'utf8'),
    readFile(fileURLToPath(new URL('styles.css', base)), 'utf8'),
  ])
  assert.match(app, /aria-label="查看告警历史"/)
  assert.match(app, /aria-label="移动端主导航"/)
  assert.match(styles, /overflow-x:\s*hidden/)
  assert.match(styles, /@media \(max-width: 767px\)/)
})

test('price refresh uses a dedicated timeout longer than ordinary API calls', async () => {
  const apiSource = await readFile(fileURLToPath(new URL('../src/api/index.js', import.meta.url)), 'utf8')
  assert.match(apiSource, /timeout:\s*15000/)
  assert.match(apiSource, /PRICE_REFRESH_TIMEOUT_MS\s*=\s*60000/)
  assert.match(apiSource, /\/prices\/refresh[\s\S]*timeout:\s*PRICE_REFRESH_TIMEOUT_MS/)
})
