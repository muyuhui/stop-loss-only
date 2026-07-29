import assert from 'node:assert/strict'
import test from 'node:test'

import { formatMoney } from '../src/utils/format.js'
import { monitoringTrust, quoteAge, quoteTrust } from '../src/utils/quoteTrust.js'


test('missing prices are never formatted as zero', () => {
  assert.equal(formatMoney(null), '--')
  assert.equal(formatMoney(undefined), '--')
  assert.equal(formatMoney(0), '¥0.00')
})

test('quote trust uses backend state and exposes deterministic age', () => {
  const now = Date.parse('2026-07-23T02:05:00Z')
  const trust = quoteTrust({ quote_state: 'delayed', quoted_at: '2026-07-23T02:03:00Z', is_actionable: true }, now)
  assert.deepEqual(trust, { state: 'delayed', label: '延迟', tone: 'warning', age: '2 分钟前', actionable: true, text: '延迟 · 2 分钟前' })
  assert.equal(quoteAge(null, now), '无时间')
  assert.equal(quoteTrust({ quote_state: 'unpriced' }, now).actionable, false)
  assert.equal(quoteTrust({ quote_state: 'unpriced' }, now).label, '未定价')
})

test('monitoring trust summarizes healthy, degraded and missing cycles', () => {
  assert.equal(monitoringTrust({}).tone, 'warning')
  assert.equal(monitoringTrust({ latest_cycle: { status: 'success' }, freshness: 'healthy', overdue: false, actionable_quote_coverage_pct: 100 }).tone, 'success')
  assert.equal(monitoringTrust({ latest_cycle: { status: 'partial' }, overdue: false, quote_coverage_pct: 50 }).tone, 'warning')
  assert.equal(monitoringTrust({ latest_cycle: { status: 'success' }, overdue: true, quote_coverage_pct: 20 }).tone, 'danger')
  const closed = monitoringTrust({
    latest_cycle: { status: 'skipped' },
    freshness: 'market_closed',
    overdue: false,
    actionable_quote_coverage_pct: 0,
    valuation_quote_coverage_pct: 100,
    last_success_at: '2026-07-23T02:00:00Z',
  })
  assert.equal(closed.tone, 'muted')
  assert.equal(closed.title, '市场休市')
  assert.match(closed.detail, /最近可操作行情/)
  assert.match(monitoringTrust({
    latest_cycle: { status: 'success' },
    freshness: 'healthy',
    actionable_quote_coverage_pct: null,
  }).detail, /--/)
})
