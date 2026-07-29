import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import api, { requestHoldingHistory } from '../src/api'
import Dashboard from '../src/views/Dashboard.vue'
import HoldingDetail from '../src/views/HoldingDetail.vue'
import Settings from '../src/views/Settings.vue'
import { useRuntimeCapabilitiesStore } from '../src/stores/runtimeCapabilities'

vi.mock('../src/api', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() },
  requestHoldingHistory: vi.fn(),
  requestPriceRefresh: vi.fn(),
  refreshErrorMessage: vi.fn(() => '价格刷新失败，请稍后重试。'),
}))

const dashboardData = {
  active_cost: 1000, active_market_value: 1100, unrealized_profit_loss: 100,
  unrealized_profit_loss_pct: 10, realized_profit_loss: 0, holding_count: 1,
  triggered_count: 0, closed_count: 0, active_alerts_count: 0, today_alert_count: 0,
  latest_alert: null, actionable_position_coverage_pct: 100, valuation_coverage_pct: 100,
  holdings: [{ id: 12, code: '000001', name: '权威持仓', type: 'stock', current_price: 11,
    stop_loss_price: 9, stop_loss_distance_pct: 18, profit_loss_pct: 10, status: 'holding',
    quote_state: 'live', is_actionable: true }],
}
const holdingData = {
  id: 12, code: '000001', name: '权威持仓', type: 'stock', buy_price: 10, quantity: 100,
  current_price: 11, highest_price: 11, stop_loss_method: 'fixed', stop_loss_value: 9,
  stop_loss_price: 9, stop_loss_distance_pct: 18, profit_loss_pct: 10, status: 'holding',
  quote_state: 'live', is_actionable: true, updated_at: '2026-07-24T08:00:00Z',
}

const stubs = {
  DataState: { props: ['title'], template: '<div>{{ title }}</div>' },
  HoldingPriceChart: true,
  ElButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
  ElTag: { template: '<span><slot /></span>' },
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: { data: () => ({ row: dashboardData.holdings[0] }), template: '<div><slot :row="row" /></div>' },
  ElInputNumber: true,
  ElInput: true,
  ElSelect: { template: '<select><slot /></select>' },
  ElOption: true,
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<label><slot /></label>' },
}

async function mountAt(component, path, routes = [], capabilities = null) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path, component }, { path: '/holdings', component: { template: '<p>持仓列表</p>' } }, ...routes],
  })
  await router.push(path.replace(':id', '12'))
  await router.isReady()
  const pinia = createPinia()
  if (capabilities === 'error') {
    const store = useRuntimeCapabilitiesStore(pinia)
    store.status = 'error'
    store.error = '能力发现失败'
  } else if (capabilities) {
    useRuntimeCapabilitiesStore(pinia).apply({
      authority_stage: 'legacy', stable_runtime_supported: true, capabilities,
    })
  }
  const wrapper = mount(component, { global: { plugins: [pinia, router], stubs } })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockImplementation((path) => {
    if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
    if (path === '/dashboard') return Promise.resolve({ data: dashboardData })
    if (path === '/monitoring/status') return Promise.resolve({ data: { scheduler_running: true, overdue: false, quote_coverage_pct: 100 } })
    if (path === '/holdings/12') return Promise.resolve({ data: holdingData })
    return Promise.resolve({ data: {} })
  })
  api.put.mockResolvedValue({ data: { poll_interval: 30, monitor_interval: 5 } })
  api.post.mockResolvedValue({ data: {} })
  requestHoldingHistory.mockResolvedValue({ data: { points: [] } })
})

afterEach(() => vi.restoreAllMocks())

describe('受支持视图真实挂载', () => {
  it('Dashboard 后台失败时保留最后成功数据且只拥有一个轮询计时器', async () => {
    const setInterval = vi.spyOn(globalThis, 'setInterval')
    const clearInterval = vi.spyOn(globalThis, 'clearInterval')
    const { wrapper } = await mountAt(Dashboard, '/')
    expect(wrapper.text()).toContain('权威持仓')
    expect(api.get.mock.calls.some(([path]) => path === '/risk/budget')).toBe(false)
    expect(wrapper.text()).not.toContain('风险预算')
    expect(setInterval).toHaveBeenCalledTimes(1)

    api.get.mockImplementation((path) => path === '/dashboard'
      ? Promise.reject(new Error('background failure'))
      : Promise.resolve({ data: path === '/settings' ? { poll_interval: 30, monitor_interval: 5 } : {} }))
    await wrapper.findAll('button').find((button) => button.text() === '刷新').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('权威持仓')
    expect(wrapper.text()).toContain('最后一次成功数据')
    wrapper.unmount()
    expect(clearInterval).toHaveBeenCalled()
  })

  it('HoldingDetail 从 URL 恢复 legacy 持仓并提供手动平仓', async () => {
    const { wrapper } = await mountAt(HoldingDetail, '/holdings/:id')
    expect(api.get).toHaveBeenCalledWith('/holdings/12')
    expect(requestHoldingHistory).toHaveBeenCalledWith('12', '3m')
    expect(wrapper.text()).toContain('权威持仓')
    expect(wrapper.text()).toContain('手动平仓')
  })

  it('HoldingDetail 对未定价持仓显示未知语义而不是零风险', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/holdings/12') return Promise.resolve({ data: {
        ...holdingData, current_price: null, profit_loss_pct: null,
        stop_loss_distance_pct: null, quote_state: 'unpriced', is_actionable: false,
      } })
      return Promise.resolve({ data: path === '/settings' ? { poll_interval: 30, monitor_interval: 5 } : {} })
    })
    const { wrapper } = await mountAt(HoldingDetail, '/holdings/:id')
    expect(wrapper.text()).toContain('未定价')
    expect(wrapper.text()).toContain('风险未知')
    expect(wrapper.text()).not.toContain('0.00%')
  })

  it('Settings 只显示可应用的稳定控制', async () => {
    const { wrapper } = await mountAt(Settings, '/settings')
    const text = wrapper.text()
    expect(text).toContain('刷新频率')
    expect(text).toContain('运行时诊断')
    expect(text).toContain('数据库备份')
    expect(text).not.toContain('风险预算')
    expect(text).not.toMatch(/CSV|Webhook|Browser notifications|retention/i)
    await wrapper.findAll('button').find(button => button.text() === '保存并应用').trigger('click')
    await flushPromises()
    expect(api.put).toHaveBeenCalledWith('/settings', { poll_interval: 30, monitor_interval: 5 })
  })

  it('Settings 仅在风险能力可用时显示并保存风险政策', async () => {
    const { wrapper } = await mountAt(Settings, '/settings', [], { risk_budget_reads: true })
    expect(wrapper.text()).toContain('风险预算')
    expect(wrapper.text()).toContain('组合权益')
    await wrapper.findAll('button').find(button => button.text() === '保存风险与运行设置').trigger('click')
    await flushPromises()
    expect(api.put).toHaveBeenCalledWith('/settings', expect.objectContaining({
      poll_interval: 30,
      monitor_interval: 5,
      portfolio_equity: null,
      portfolio_risk_limit_pct: 5,
      default_position_risk_limit_pct: 1,
    }))
  })

  it('Settings 在能力发现失败时默认关闭风险政策并只保存监控设置', async () => {
    const { wrapper } = await mountAt(Settings, '/settings', [], 'error')
    expect(wrapper.text()).not.toContain('风险预算')
    await wrapper.findAll('button').find(button => button.text() === '保存并应用').trigger('click')
    await flushPromises()
    expect(api.put).toHaveBeenCalledWith('/settings', { poll_interval: 30, monitor_interval: 5 })
  })

  it('Dashboard 对全部未定价持仓显示风险待定并避免虚假零距离', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
      if (path === '/dashboard') return Promise.resolve({ data: {
        ...dashboardData,
        holdings: [{ ...dashboardData.holdings[0], current_price: null, profit_loss_pct: null,
          stop_loss_distance_pct: null, quote_state: 'unpriced', is_actionable: false }],
      } })
      if (path === '/monitoring/status') return Promise.resolve({ data: {
        scheduler_running: true, overdue: false,
        actionable_quote_coverage_pct: 0, valuation_quote_coverage_pct: 0,
      } })
      return Promise.resolve({ data: {} })
    })
    const { wrapper } = await mountAt(Dashboard, '/')
    expect(wrapper.text()).toContain('风险状态待定')
    const card = wrapper.get('.holding-card')
    expect(card.text()).toContain('未定价')
    expect(card.text()).toContain('风险未知')
    expect(card.text()).not.toContain('0.00%')
    wrapper.unmount()
  })

  it('Dashboard 在空组合覆盖率未知时显示暂无活动持仓', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
      if (path === '/dashboard') return Promise.resolve({ data: {
        ...dashboardData, holding_count: 0, triggered_count: 0, holdings: [],
        actionable_position_coverage_pct: null, valuation_coverage_pct: null,
      } })
      if (path === '/monitoring/status') return Promise.resolve({ data: {
        scheduler_running: true, overdue: false,
        actionable_quote_coverage_pct: null, valuation_quote_coverage_pct: null,
      } })
      return Promise.resolve({ data: {} })
    })
    const { wrapper } = await mountAt(Dashboard, '/')
    expect(wrapper.text()).toContain('可操作行情覆盖：暂无活动持仓')
    expect(wrapper.text()).toContain('估值行情覆盖：暂无活动持仓')
    wrapper.unmount()
  })
})
