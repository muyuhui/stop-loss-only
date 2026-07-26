import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../src/api'
import RiskPlanner from '../src/views/RiskPlanner.vue'

vi.mock('../src/api', () => ({ default: { post: vi.fn() } }))

const stubs = {
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<label><slot /></label>' },
  ElButton: {
    props: ['nativeType'],
    emits: ['click'],
    template: '<button :type="nativeType === \'submit\' ? \'submit\' : \'button\'" @click="$emit(\'click\')"><slot /></button>',
  },
  ElInput: { template: '<input />' },
  ElInputNumber: { template: '<input type="number" />' },
  ElSelect: { template: '<select><slot /></select>' },
  ElOption: { template: '<option />' },
  ElRadioGroup: { template: '<div><slot /></div>' },
  ElRadio: { template: '<span><slot /></span>' },
}

const readyPlan = {
  status: 'ready',
  reason_code: null,
  normalized_input: {
    code: '000001', name: '甲', asset_type: 'stock', entry_price: '20',
    stop_method: 'fixed', stop_value: '18',
  },
  budget: { status: 'available' },
  initial_stop_price: '18', effective_position_risk_limit_pct: '1',
  portfolio_limit_amount: '5000', position_limit_amount: '1000',
  remaining_portfolio_capacity: '5000', allowed_plan_risk: '1000',
  entry_fees: '5', estimated_exit_fees: '5', unit_price_risk: '2',
  raw_quantity: '495', quantity_increment: '100', recommended_quantity: '400',
  projected_loss_at_stop: '810', required_capital: '8005',
}

async function mounted() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/planner', component: RiskPlanner },
      { path: '/settings', component: { template: '<div />' } },
      { path: '/holdings/:id', component: { template: '<div />' } },
    ],
  })
  await router.push('/planner')
  await router.isReady()
  return mount(RiskPlanner, { global: { plugins: [router], stubs } })
}

beforeEach(() => vi.clearAllMocks())

describe('risk planner workflow', () => {
  it('previews without creating and requires a second explicit confirmation', async () => {
    api.post.mockResolvedValueOnce({ data: readyPlan }).mockResolvedValueOnce({ data: { id: 7 } })
    const wrapper = await mounted()
    Object.assign(wrapper.vm.form, {
      code: '000001', name: '甲', asset_type: 'stock', entry_price: 20,
      stop_method: 'fixed', stop_value: 18, entry_fees: 5, estimated_exit_fees: 5,
    })
    await wrapper.vm.preview()
    await flushPromises()
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.post.mock.calls[0][0]).toBe('/risk/plans/preview')
    expect(wrapper.text()).toContain('400 股')
    expect(wrapper.text()).toContain('没有提交任何订单')

    const continueButton = wrapper.findAll('button').find(item => item.text().includes('继续填写'))
    await continueButton.trigger('click')
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('风险容量不会因试算而锁定')
    const createButton = wrapper.findAll('button').find(item => item.text().includes('确认创建仓位'))
    await createButton.trigger('click')
    await flushPromises()
    expect(api.post.mock.calls[1][0]).toBe('/positions')
    expect(api.post.mock.calls[1][1].quantity).toBe('400')
  })

  it('shows incomplete coverage without rendering a zero recommendation', async () => {
    api.post.mockResolvedValue({ data: {
      ...readyPlan, status: 'refused', reason_code: 'portfolio_risk_coverage_incomplete',
      recommended_quantity: null, remaining_portfolio_capacity: null,
    } })
    const wrapper = await mounted()
    Object.assign(wrapper.vm.form, { code: '000001', name: '甲', entry_price: 20, stop_value: 18 })
    await wrapper.vm.preview()
    await flushPromises()
    expect(wrapper.text()).toContain('没有有效止损规则')
    expect(wrapper.text()).not.toContain('建议最大数量')
  })

  it('keeps the empty state recoverable after a request failure', async () => {
    api.post.mockRejectedValue(new Error('offline'))
    const wrapper = await mounted()
    await wrapper.vm.preview()
    await flushPromises()
    expect(wrapper.text()).toContain('填写计划参数后开始试算')
  })

  it('renders fund precision and zero-increment refusal from server results', async () => {
    api.post.mockResolvedValueOnce({ data: {
      ...readyPlan,
      normalized_input: { ...readyPlan.normalized_input, asset_type: 'fund' },
      recommended_quantity: '12.345678',
      quantity_increment: '0.000001',
    } }).mockResolvedValueOnce({ data: {
      ...readyPlan, status: 'refused', reason_code: 'quantity_below_minimum_increment',
      recommended_quantity: null,
    } })
    const wrapper = await mounted()
    wrapper.vm.form.asset_type = 'fund'
    await wrapper.vm.preview()
    await flushPromises()
    expect(wrapper.text()).toContain('12.345678 份')
    await wrapper.vm.preview()
    await flushPromises()
    expect(wrapper.text()).toContain('最小建仓数量')
  })
})
