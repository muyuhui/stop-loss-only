import test from 'node:test'
import assert from 'node:assert/strict'

import { holdingStatusLabel, holdingStatusTag } from '../src/utils/holdingStatus.js'
import { summarizeRefresh } from '../src/utils/refreshResult.js'

test('holding lifecycle states have distinct labels and tags', () => {
  assert.deepEqual(
    ['holding', 'triggered', 'closed'].map(status => [holdingStatusLabel(status), holdingStatusTag(status)]),
    [['持有中', 'success'], ['已触发', 'danger'], ['已关闭', 'info']],
  )
})

test('partial refresh never reports failed instruments as successful', () => {
  const summary = summarizeRefresh({
    status: 'partial', triggered: [],
    items: [{ code: '000001', fresh: true, error: null }, { code: '000002', fresh: false, error: 'timeout' }],
  })
  assert.equal(summary.type, 'warning')
  assert.match(summary.message, /000002/)
  assert.doesNotMatch(summary.message, /刷新完成/)
})
