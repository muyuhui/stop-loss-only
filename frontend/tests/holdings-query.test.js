import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DEFAULT_HOLDINGS_SORT,
  HOLDINGS_SORT_KEY,
  loadHoldingsSort,
  normalizeHoldingsSort,
  saveHoldingsSort,
} from '../src/utils/holdingsQuery.js'


function fakeStorage(initial = {}) {
  const map = new Map(Object.entries(initial))
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
  }
}

test('normalizeHoldingsSort 只接受约定枚举', () => {
  for (const value of ['newest', 'name', 'risk']) {
    assert.equal(normalizeHoldingsSort(value), value)
  }
  assert.equal(normalizeHoldingsSort('profit'), DEFAULT_HOLDINGS_SORT)
  assert.equal(normalizeHoldingsSort(undefined), DEFAULT_HOLDINGS_SORT)
  assert.equal(normalizeHoldingsSort(null), DEFAULT_HOLDINGS_SORT)
})

test('loadHoldingsSort 读取并校验存储值', () => {
  assert.equal(loadHoldingsSort(fakeStorage({ [HOLDINGS_SORT_KEY]: 'risk' })), 'risk')
  assert.equal(loadHoldingsSort(fakeStorage({ [HOLDINGS_SORT_KEY]: 'bogus' })), DEFAULT_HOLDINGS_SORT)
  assert.equal(loadHoldingsSort(fakeStorage({})), DEFAULT_HOLDINGS_SORT)
})

test('saveHoldingsSort 写入规范化后的值', () => {
  const storage = fakeStorage()
  saveHoldingsSort('risk', storage)
  assert.equal(storage.getItem(HOLDINGS_SORT_KEY), 'risk')
  saveHoldingsSort('bogus', storage)
  assert.equal(storage.getItem(HOLDINGS_SORT_KEY), DEFAULT_HOLDINGS_SORT)
})

test('存储不可用时读取与写入都不抛错', () => {
  const broken = {
    getItem: () => { throw new Error('denied') },
    setItem: () => { throw new Error('denied') },
  }
  assert.equal(loadHoldingsSort(broken), DEFAULT_HOLDINGS_SORT)
  saveHoldingsSort('risk', broken) // 不应抛出
})
