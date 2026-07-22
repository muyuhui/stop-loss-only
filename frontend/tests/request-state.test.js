import test from 'node:test'
import assert from 'node:assert/strict'

import { formatMoney, formatSignedPercent, stopLossRisk, valueTone } from '../src/utils/format.js'
import { useRequestState } from '../src/utils/requestState.js'

test('financial formatting keeps signs and non-color risk labels', () => {
  assert.equal(formatMoney(12.5), '¥12.50')
  assert.equal(formatSignedPercent(3.2), '+3.20%')
  assert.equal(formatSignedPercent(-1.25), '-1.25%')
  assert.equal(valueTone(3.2), 'profit')
  assert.deepEqual(stopLossRisk(2.5), { level: 'danger', label: '非常接近止损' })
  assert.deepEqual(stopLossRisk(10), { level: 'safe', label: '距离安全' })
})

test('request state preserves data during refresh failures and detects staleness', () => {
  let current = 1_000
  const state = useRequestState({ now: () => current })
  state.begin()
  assert.equal(state.initialLoading.value, true)
  state.succeed()
  assert.equal(state.hasData.value, true)
  assert.equal(state.lastUpdatedAt.value, 1_000)

  state.begin()
  assert.equal(state.refreshing.value, true)
  state.fail('网络中断')
  assert.equal(state.hasData.value, true)
  assert.equal(state.error.value, '网络中断')

  current = 62_001
  assert.equal(state.isStale(30), true)
})
