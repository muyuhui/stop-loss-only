import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../src/api'
import Dashboard from '../src/views/Dashboard.vue'
import { useRuntimeCapabilitiesStore } from '../src/stores/runtimeCapabilities'

vi.mock('../src/api', () => ({ default: { get: vi.fn() } }))

const stubs = {
  DataState: { props: ['title'], template: '<div>{{ title }}</div>' },
  ElButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
  ElTag: { template: '<span><slot /></span>' },
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: { template: '<div />' },
}

function ledgerPayload(overrides = {}) {
  return {
    active_cost: 10000, active_market_value: 9200, unrealized_profit_loss: -800,
    unrealized_profit_loss_pct: -8, realized_profit_loss: -100,
    month_summary: {
      month: '2026-08', realized_profit_loss: -100, closed_count: 1,
      triggered_count: 2, stop_adjustment_count: 3, stop_lowered_count: 1,
      largest_loss: { name: '最大亏损', code: '000001', profit_loss_amount: -200 },
    },
    holding_count: 2, triggered_count: 2, closed_count: 1, active_alerts_count: 0,
    today_alert_count: 0, latest_alert: null, holdings: [],
    ...overrides,
  }
}

async function mountDashboard(payload) {
  api.get.mockImplementation((url) => {
    if (url === '/dashboard') return Promise.resolve({ data: payload })
    if (url === '/monitoring/status') return Promise.resolve({ data: {} })
    return Promise.resolve({ data: {} })
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Dashboard },
      { path: '/alerts', component: { template: '<p>alerts</p>' } },
      { path: '/holdings', component: { template: '<p>holdings</p>' } },
      { path: '/settings', component: { template: '<p>settings</p>' } },
      { path: '/planner', component: { template: '<p>planner</p>' } },
    ],
  })
  await router.push('/')
  await router.isReady()
  const pinia = createPinia()
  useRuntimeCapabilitiesStore(pinia).apply({
    authority_stage: 'legacy', stable_runtime_supported: true, capabilities: {},
  })
  const wrapper = mount(Dashboard, { global: { plugins: [pinia, router], stubs } })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('本月账本卡片', () => {
  it('渲染主导数字、辅助行与最大亏损来源', async () => {
    const { wrapper } = await mountDashboard(ledgerPayload())
    const text = wrapper.text()
    expect(text).toContain('本月账本')
    expect(text).toContain('本月已实现盈亏')
    expect(text).toContain('¥-100.00')
    expect(text).toContain('平仓 1 笔')
    expect(text).toContain('本月触发 2 次')
    expect(text).toContain('调整止损 3 次（调低 1）')
    expect(text).toContain('最大亏损来源：最大亏损（000001）')
    expect(text).toContain('¥-200.00')
    expect(text).toContain('当前浮亏（快照）')
    expect(text).toContain('¥-800.00')
    expect(wrapper.get('.month-ledger')).toBeTruthy()
  })

  it('有待处置时显示去处置入口并跳转告警页', async () => {
    const { wrapper, router } = await mountDashboard(ledgerPayload())
    await wrapper.findAll('button').find((button) => button.text() === '去处置').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/alerts')
  })

  it('无待处置时不显示去处置入口', async () => {
    const { wrapper } = await mountDashboard(ledgerPayload({ triggered_count: 0 }))
    expect(wrapper.text()).toContain('无待处置')
    expect(wrapper.text()).not.toContain('去处置')
  })

  it('month_summary 缺失时不渲染卡片', async () => {
    const { wrapper } = await mountDashboard(ledgerPayload({ month_summary: null }))
    expect(wrapper.text()).not.toContain('本月账本')
  })

  it('空组合显示零值账本', async () => {
    const { wrapper } = await mountDashboard(ledgerPayload({
      unrealized_profit_loss: 0,
      month_summary: {
        month: '2026-08', realized_profit_loss: 0, closed_count: 0,
        triggered_count: 0, stop_adjustment_count: 0, stop_lowered_count: 0,
        largest_loss: null,
      },
      triggered_count: 0,
    }))
    const text = wrapper.text()
    expect(text).toContain('平仓 0 笔')
    expect(text).toContain('本月触发 0 次')
    expect(text).toContain('无待处置')
  })
})
