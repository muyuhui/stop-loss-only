import test from 'node:test'
import assert from 'node:assert/strict'

import { formatMarketSession, formatQuoteFreshness, quoteFreshnessText } from '../src/utils/market.js'


test('formatMarketSession 映射全部时段且未知返回 null', () => {
  assert.equal(formatMarketSession('pre_market'), '盘前')
  assert.equal(formatMarketSession('open'), '交易中')
  assert.equal(formatMarketSession('lunch'), '午休')
  assert.equal(formatMarketSession('closed'), '已收盘')
  assert.equal(formatMarketSession('unknown'), null)
  assert.equal(formatMarketSession(undefined), null)
  assert.equal(formatMarketSession(null), null)
})

test('formatQuoteFreshness 边界：刚刚、N 分钟前、绝对时间', () => {
  const now = Date.parse('2026-08-04T10:00:00+08:00')
  assert.equal(formatQuoteFreshness('2026-08-04T10:00:30+08:00', now), '刚刚')
  assert.equal(formatQuoteFreshness('2026-08-04T09:59:31+08:00', now), '刚刚')
  assert.equal(formatQuoteFreshness('2026-08-04T09:30:00+08:00', now), '30 分钟前')
  assert.match(formatQuoteFreshness('2026-08-04T08:00:00+08:00', now), /08:00:00/)
})

test('formatQuoteFreshness 无效输入返回 null', () => {
  assert.equal(formatQuoteFreshness(null), null)
  assert.equal(formatQuoteFreshness(undefined), null)
  assert.equal(formatQuoteFreshness('not-a-date'), null)
})

test('quoteFreshnessText 有行情带前缀，无行情显示未定价', () => {
  assert.match(quoteFreshnessText('2026-08-04T10:00:00+08:00'), /^行情 /)
  assert.equal(quoteFreshnessText(null), '未定价/行情不可用')
})
