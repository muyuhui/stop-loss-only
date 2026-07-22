import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

import { buildHistoryChartOption, HISTORY_RANGES, historySummary } from '../src/utils/historyChart.js'

const data = {
  buy_price: 10,
  stop_loss_method: 'trailing',
  points: [
    { trade_date: '2026-07-20', price: 10, stop_loss_price: 9, triggered: false },
    { trade_date: '2026-07-21', price: 12, stop_loss_price: 10.8, triggered: false },
    { trade_date: '2026-07-22', price: 10.5, stop_loss_price: 10.8, triggered: true },
  ],
}

test('history ranges and summary remain compact and deterministic', () => {
  assert.deepEqual(HISTORY_RANGES.map(item => item.value), ['1m', '3m', '6m', '1y'])
  assert.deepEqual(historySummary(data.points), { latest: 10.5, highest: 12, lowest: 10, stopLoss: 10.8 })
  assert.equal(historySummary([]), null)
})

test('chart option expresses price, trailing stop, buy line and trigger marker', () => {
  const option = buildHistoryChartOption(data, value => `¥${value}`)
  assert.equal(option.series[0].name, '价格')
  assert.equal(option.series[0].markLine.data[0].yAxis, 10)
  assert.equal(option.series[0].markPoint.data.length, 1)
  assert.equal(option.series[1].step, 'end')
  assert.deepEqual(option.series[1].data, [9, 10.8, 10.8])
})

test('holding detail keeps history loading independent and guards stale responses', () => {
  const detail = fs.readFileSync(new URL('../src/views/HoldingDetail.vue', import.meta.url), 'utf8')
  const chart = fs.readFileSync(new URL('../src/components/HoldingPriceChart.vue', import.meta.url), 'utf8')
  assert.match(detail, /historyRequestId/)
  assert.match(detail, /requestId !== historyRequestId/)
  assert.match(detail, /<HoldingPriceChart/)
  assert.match(chart, /止损线按当前规则计算/)
  assert.match(chart, /ResizeObserver/)
  assert.match(chart, /@media \(max-width: 767px\)/)
})
