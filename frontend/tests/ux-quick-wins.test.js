import test from 'node:test'
import assert from 'node:assert/strict'

import { estimateRealizedProfitLoss } from '../src/utils/format.js'
import { holdingPrefillFromPlan } from '../src/utils/holdingForm.js'

test('平仓预览只对有效输入计算毛盈亏并返回 null 兜底', () => {
  assert.equal(estimateRealizedProfitLoss(11, 10, 100), 100)
  assert.equal(estimateRealizedProfitLoss('12', '10', 100), 200)
  assert.equal(estimateRealizedProfitLoss(9, 10, 100), -100)
  assert.equal(estimateRealizedProfitLoss(0, 10, 100), null)
  assert.equal(estimateRealizedProfitLoss(null, 10, 100), null)
  assert.equal(estimateRealizedProfitLoss('', 10, 100), null)
  assert.equal(estimateRealizedProfitLoss(10, 10, 0), null)
  assert.equal(estimateRealizedProfitLoss('abc', 10, 100), null)
})

test('试算结果映射为整数持仓预填并保留资产精度', () => {
  const plan = {
    status: 'ready',
    normalized_input: {
      code: ' 000001 ', name: ' 平安银行 ', asset_type: 'stock',
      entry_price: '20.1234', stop_method: 'fixed', stop_value: '18',
    },
    recommended_quantity: '400',
  }
  const prefill = holdingPrefillFromPlan(plan)
  assert.equal(prefill.code, '000001')
  assert.equal(prefill.name, '平安银行')
  assert.equal(prefill.type, 'stock')
  assert.equal(prefill.buy_price, 20.12)
  assert.equal(prefill.quantity, 400)
  assert.equal(prefill.stop_loss_method, 'fixed')
  assert.equal(prefill.stop_loss_value, 18)
  assert.match(prefill.buy_date, /^\d{4}-\d{2}-\d{2}$/)
})

test('基金推荐数量向下取整为整数份且买入价按基金精度取整', () => {
  const plan = {
    status: 'ready',
    normalized_input: {
      code: '110011', name: '易方达示例', asset_type: 'fund',
      entry_price: '1.23456', stop_method: 'percentage', stop_value: '10',
    },
    recommended_quantity: '12.999',
  }
  const prefill = holdingPrefillFromPlan(plan)
  assert.equal(prefill.type, 'fund')
  assert.equal(prefill.quantity, 12)
  assert.equal(prefill.buy_price, 1.235)
})

test('试算预填在输入缺失或数量不足时返回 null', () => {
  assert.equal(holdingPrefillFromPlan(null), null)
  assert.equal(holdingPrefillFromPlan({ normalized_input: {}, recommended_quantity: '100' }), null)
  assert.equal(holdingPrefillFromPlan({
    normalized_input: {
      code: '000001', name: '甲', asset_type: 'stock',
      entry_price: '20', stop_method: 'unknown', stop_value: '18',
    },
    recommended_quantity: '100',
  }), null)
  assert.equal(holdingPrefillFromPlan({
    normalized_input: {
      code: '000001', name: '甲', asset_type: 'stock',
      entry_price: '20', stop_method: 'fixed', stop_value: '18',
    },
    recommended_quantity: '0.5',
  }), null)
})
