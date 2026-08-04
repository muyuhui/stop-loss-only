import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../src/api'
import { useRuntimeCapabilitiesStore } from '../src/stores/runtimeCapabilities'
import RiskPlanner from '../src/views/RiskPlanner.vue'

vi.mock('../src/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

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
  plan_kind: 'new', status: 'ready', reason_code: null, calculated_at: '2026-07-30T02:00:00Z',
  normalized_input: {
    code: '000001', name: '甲', asset_type: 'stock', entry_price: '20',
    stop_method: 'fixed', stop_value: '18',
  },
  budget: { status: 'available' }, initial_stop_price: '18',
  effective_position_risk_limit_pct: '1', portfolio_limit_amount: '5000',
  position_limit_amount: '1000', remaining_portfolio_capacity: '5000',
  allowed_plan_risk: '1000', entry_fees: '5', estimated_exit_fees: '5',
  unit_price_risk: '2', raw_quantity: '495', quantity_increment: '100',
  recommended_quantity: '400', projected_loss_at_stop: '810', required_capital: '8005',
  post_plan_portfolio_used_risk: '810', post_plan_portfolio_utilization_pct: '16.2',
}

const holding = {
  id: 12, code: '000001', name: '甲', type: 'stock', status: 'holding',
  quantity: 100, buy_price: 10, stop_loss_price: 9, current_price: 10,
  quote_state: 'live', is_actionable: true,
}

const readyAddOnPlan = {
  plan_kind: 'add_on', status: 'ready', reason_code: null, calculated_at: '2026-07-30T02:05:00Z',
  holding: { ...holding, asset_type: 'stock', quantity: '100', buy_price: '10', stop_loss_price: '9' },
  budget: { status: 'available' }, planned_entry_price: '10', existing_stop_price: '9',
  current_holding_risk: '100', effective_position_risk_limit_pct: '1',
  position_limit_amount: '1000', remaining_position_capacity: '900',
  remaining_portfolio_capacity: '1200', allowed_incremental_risk: '900',
  entry_fees: '5', estimated_exit_fees: '5', unit_price_risk: '1', raw_quantity: '890',
  quantity_increment: '100', recommended_quantity: '800', incremental_projected_loss: '810',
  required_capital: '8005', post_plan_holding_risk: '910',
  post_plan_portfolio_used_risk: '1610', post_plan_portfolio_utilization_pct: '32.2',
}

async function mounted({ preview = true, creation = false, path = '/planner' } = {}) {
  const pinia = createPinia()
  useRuntimeCapabilitiesStore(pinia).apply({
    authority_stage: creation ? 'new-authoritative' : 'legacy',
    stable_runtime_supported: !creation,
    capabilities: {
      risk_plan_previews: preview,
      risk_covered_position_creation: creation,
      legacy_holding_writes: !creation,
    },
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/planner', component: RiskPlanner },
      { path: '/settings', component: { template: '<div />' } },
      { path: '/holdings', component: { template: '<div />' } },
      { path: '/holdings/:id', component: { template: '<div />' } },
    ],
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(RiskPlanner, { global: { plugins: [pinia, router], stubs } })
  await flushPromises()
  return { wrapper, router }
}

function fillNewPlan(wrapper, assetType = 'stock') {
  Object.assign(wrapper.vm.form, {
    code: '000001', name: '甲', asset_type: assetType, entry_price: 20,
    stop_method: 'fixed', stop_value: 18, entry_fees: 5, estimated_exit_fees: 5,
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockResolvedValue({ data: holding })
})

describe('risk planner workflow', () => {
  it('renders an unavailable direct route without issuing requests', async () => {
    const { wrapper } = await mounted({ preview: false })
    await wrapper.vm.preview()
    await wrapper.vm.createPosition()
    expect(wrapper.text()).toContain('当前运行模式未启用风险试算')
    expect(wrapper.text()).toContain('返回持仓管理')
    expect(api.get).not.toHaveBeenCalled()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('keeps the stable runtime preview-only with no position write command', async () => {
    api.post.mockResolvedValue({ data: readyPlan })
    const { wrapper } = await mounted()
    fillNewPlan(wrapper)
    await wrapper.vm.preview()
    await flushPromises()
    expect(api.post).toHaveBeenCalledOnce()
    expect(api.post).toHaveBeenCalledWith('/risk/plans/preview', expect.any(Object))
    expect(wrapper.text()).toContain('风险约束下的最大数量')
    expect(wrapper.text()).toContain('400 股')
    expect(wrapper.text()).toContain('没有提交任何订单')
    expect(wrapper.text()).not.toContain('继续填写建仓确认')
    expect(api.post.mock.calls.some(([path]) => path === '/positions')).toBe(false)
  })

  it('requires a second explicit confirmation when position creation is available', async () => {
    api.post.mockResolvedValueOnce({ data: readyPlan }).mockResolvedValueOnce({ data: { id: 7 } })
    const { wrapper } = await mounted({ creation: true })
    fillNewPlan(wrapper)
    await wrapper.vm.preview()
    await flushPromises()
    const continueButton = wrapper.findAll('button').find(item => item.text().includes('继续填写'))
    await continueButton.trigger('click')
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('风险容量不会因试算而锁定')
    const createButton = wrapper.findAll('button').find(item => item.text().includes('确认创建仓位'))
    await createButton.trigger('click')
    await flushPromises()
    expect(api.post.mock.calls[1][0]).toBe('/positions')
    expect(api.post.mock.calls[1][1].quantity).toBe('400')
    expect(wrapper.text()).not.toContain('填入新增持仓')
  })

  it('shows incomplete coverage without rendering a quantity', async () => {
    api.post.mockResolvedValue({ data: {
      ...readyPlan, status: 'refused', reason_code: 'portfolio_risk_coverage_incomplete',
      recommended_quantity: null, remaining_portfolio_capacity: null,
    } })
    const { wrapper } = await mounted()
    fillNewPlan(wrapper)
    await wrapper.vm.preview()
    await flushPromises()
    expect(wrapper.text()).toContain('存在无法计算止损风险的活动持仓')
    expect(wrapper.text()).not.toContain('400 股')
  })

  it('keeps the empty state recoverable after a request failure', async () => {
    api.post.mockRejectedValue(new Error('offline'))
    const { wrapper } = await mounted()
    fillNewPlan(wrapper)
    await wrapper.vm.preview()
    await flushPromises()
    expect(wrapper.text()).toContain('填写计划参数后开始试算')
  })

  it('renders fund precision and minimum-increment refusal from server results', async () => {
    api.post.mockResolvedValueOnce({ data: {
      ...readyPlan,
      normalized_input: { ...readyPlan.normalized_input, asset_type: 'fund' },
      recommended_quantity: '12.345678', quantity_increment: '0.000001',
    } }).mockResolvedValueOnce({ data: {
      ...readyPlan, status: 'refused', reason_code: 'quantity_below_minimum_increment',
      recommended_quantity: null,
    } })
    const { wrapper } = await mounted()
    fillNewPlan(wrapper, 'fund')
    await wrapper.vm.preview()
    await flushPromises()
    expect(wrapper.text()).toContain('12.345678 份')
    await wrapper.vm.preview()
    await flushPromises()
    expect(wrapper.text()).toContain('最小买入数量')
  })

  it('restores add-on context from the URL, prefills actionable quotes, and stays read-only', async () => {
    api.post.mockResolvedValue({ data: readyAddOnPlan })
    const { wrapper, router } = await mounted({ path: '/planner?mode=add-on&holding_id=12' })
    expect(router.currentRoute.value.query).toEqual({ mode: 'add-on', holding_id: '12' })
    expect(api.get).toHaveBeenCalledWith('/holdings/12')
    expect(wrapper.vm.addOnForm.planned_entry_price).toBe(10)
    expect(wrapper.text()).toContain('保留止损价')
    expect(api.post).not.toHaveBeenCalled()

    await wrapper.vm.preview()
    await flushPromises()
    expect(api.post).toHaveBeenCalledWith('/risk/plans/add-on-preview', expect.objectContaining({
      holding_id: 12, planned_entry_price: 10,
    }))
    expect(wrapper.text()).toContain('800 股')
    expect(wrapper.text()).toContain('当前持仓风险')
    expect(wrapper.text()).toContain('试算后持仓风险')
    expect(wrapper.text()).not.toContain('确认创建仓位')
  })

  it('does not prefill a non-actionable quote or submit without an explicit price', async () => {
    api.get.mockResolvedValue({ data: { ...holding, quote_state: 'stale', is_actionable: false } })
    const { wrapper } = await mounted({ path: '/planner?mode=add-on&holding_id=12' })
    expect(wrapper.vm.addOnForm.planned_entry_price).toBeNull()
    await wrapper.vm.preview()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('稳定运行面新仓结果可填入新增持仓并携带预填参数', async () => {
    api.post.mockResolvedValue({ data: readyPlan })
    const { wrapper, router } = await mounted()
    fillNewPlan(wrapper)
    await wrapper.vm.preview()
    await flushPromises()
    const prefillButton = wrapper.findAll('button').find(item => item.text() === '填入新增持仓')
    expect(prefillButton).toBeTruthy()
    await prefillButton.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/holdings')
    expect(router.currentRoute.value.query).toMatchObject({
      create: '1', code: '000001', name: '甲', type: 'stock',
      buy_price: '20', quantity: '400', stop_method: 'fixed', stop_value: '18',
    })
    expect(router.currentRoute.value.query.buy_date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('加仓试算结果保持只读，不提供填入新增持仓入口', async () => {
    api.post.mockResolvedValue({ data: readyAddOnPlan })
    const { wrapper } = await mounted({ path: '/planner?mode=add-on&holding_id=12' })
    await wrapper.vm.preview()
    await flushPromises()
    expect(wrapper.findAll('button').some(item => item.text() === '填入新增持仓')).toBe(false)
  })
})
