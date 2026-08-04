import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import api, { requestHoldingHistory, requestPriceRefresh } from '../src/api'
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
const aiReviewData = {
  summary: '近期行情与风险保持可控。', action: 'open_add_on_preview',
  reasons: [{ text: '风险容量仍为正。', facts: [{ fact_id: 'risk.portfolio_remaining', label: '组合剩余风险容量', value: '800', source: 'risk_budget' }] }],
  risk_scenarios: [{ condition: '价格接近止损', impact: '执行既定止损计划', facts: [] }],
  limitations: ['不包含新闻、财报和未来价格预测'], confidence: 'medium',
  can_open_add_on_preview: true, current_quote_state: 'live', current_quote_at: '2026-07-30T06:55:00Z',
  history_last_trade_date: '2026-07-30', generated_at: '2026-07-30T07:00:00Z',
  provider: 'deepseek', model: 'deepseek-v4-flash',
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

const stubs = {
  DataState: { props: ['title'], template: '<div>{{ title }}</div>' },
  HoldingPriceChart: true,
  ElButton: {
    props: ['nativeType'], emits: ['click'],
    template: '<button :type="nativeType === \'submit\' ? \'submit\' : \'button\'" @click="$emit(\'click\')"><slot /></button>',
  },
  ElForm: { emits: ['submit'], template: '<form @submit.prevent="$emit(\'submit\', { preventDefault() {} })"><slot /></form>' },
  ElTag: { template: '<span><slot /></span>' },
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: { data: () => ({ row: dashboardData.holdings[0] }), template: '<div><slot :row="row" /></div>' },
  ElInputNumber: true,
  ElInput: {
    props: ['modelValue'], emits: ['update:modelValue'],
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElSelect: { template: '<select><slot /></select>' },
  ElOption: true,
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
  return { wrapper, router, pinia }
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

  it('HoldingDetail 仅为活动持仓提供可恢复的加仓风险试算入口', async () => {
    const { wrapper, router } = await mountAt(
      HoldingDetail,
      '/holdings/:id',
      [{ path: '/planner', component: { template: '<p>风险试算</p>' } }],
      { risk_plan_previews: true },
    )
    const addOnButton = wrapper.findAll('button').find(button => button.text() === '加仓风险试算')
    expect(addOnButton).toBeTruthy()
    await addOnButton.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/planner')
    expect(router.currentRoute.value.query).toEqual({ mode: 'add-on', holding_id: '12' })

    api.get.mockImplementation((path) => {
      if (path === '/holdings/12') return Promise.resolve({ data: { ...holdingData, status: 'triggered' } })
      return Promise.resolve({ data: path === '/settings' ? { poll_interval: 30, monitor_interval: 5 } : {} })
    })
    const { wrapper: triggered } = await mountAt(
      HoldingDetail, '/holdings/:id', [], { risk_plan_previews: true },
    )
    expect(triggered.text()).not.toContain('加仓风险试算')
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

  it('稳定运行面的只读试算能力也会显示风险政策', async () => {
    const { wrapper } = await mountAt(Settings, '/settings', [], {
      risk_budget_reads: false,
      risk_plan_previews: true,
      risk_covered_position_creation: false,
    })
    expect(wrapper.text()).toContain('风险预算')
    expect(wrapper.text()).toContain('新仓和加仓风险试算默认使用')
    expect(wrapper.text()).not.toContain('创建仓位')
  })

  it('Dashboard 在稳定风险能力开启时展示活动持仓预算和新仓试算入口', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
      if (path === '/dashboard') return Promise.resolve({ data: dashboardData })
      if (path === '/monitoring/status') return Promise.resolve({ data: { scheduler_running: true, overdue: false, quote_coverage_pct: 100 } })
      if (path === '/risk/budget') return Promise.resolve({ data: {
        status: 'available', portfolio_equity: '100000', portfolio_risk_limit_pct: '5',
        portfolio_limit_amount: '5000', used_risk_amount: '100', remaining_capacity: '4900',
        utilization_pct: '2', covered_position_count: 1, open_position_count: 1,
      } })
      return Promise.resolve({ data: {} })
    })
    const { wrapper } = await mountAt(Dashboard, '/', [], {
      risk_budget_reads: true,
      risk_plan_previews: true,
      risk_covered_position_creation: false,
    })
    expect(api.get).toHaveBeenCalledWith('/risk/budget', expect.objectContaining({
      suppressErrorCodes: expect.any(Array),
    }))
    expect(wrapper.text()).toContain('按所有活动持仓触及止损时的预计损失统计')
    expect(wrapper.text()).toContain('新仓风险试算')
    expect(wrapper.text()).toContain('覆盖 1/1 个活动持仓')
  })

  it('Dashboard 风险预算请求失败时不显示虚假零值', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
      if (path === '/dashboard') return Promise.resolve({ data: dashboardData })
      if (path === '/monitoring/status') return Promise.resolve({ data: { scheduler_running: true, overdue: false, quote_coverage_pct: 100 } })
      if (path === '/risk/budget') return Promise.reject(new Error('offline'))
      return Promise.resolve({ data: {} })
    })
    const { wrapper } = await mountAt(Dashboard, '/', [], { risk_budget_reads: true })
    expect(wrapper.text()).toContain('风险预算暂时不可用')
    expect(wrapper.text()).toContain('未知值不会显示为零')
    expect(wrapper.text()).not.toContain('¥0.00')
  })

  it('Dashboard 明确区分组合权益未设置与风险覆盖不完整', async () => {
    let riskBudget = {
      status: 'unavailable', reason_code: 'portfolio_equity_unset', portfolio_equity: null,
      portfolio_risk_limit_pct: '5', portfolio_limit_amount: null, used_risk_amount: '100',
      remaining_capacity: null, utilization_pct: null, covered_position_count: 1,
      open_position_count: 1,
    }
    api.get.mockImplementation((path) => {
      if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
      if (path === '/dashboard') return Promise.resolve({ data: dashboardData })
      if (path === '/monitoring/status') return Promise.resolve({ data: { scheduler_running: true, overdue: false, quote_coverage_pct: 100 } })
      if (path === '/risk/budget') return Promise.resolve({ data: riskBudget })
      return Promise.resolve({ data: {} })
    })
    const { wrapper } = await mountAt(Dashboard, '/', [], { risk_budget_reads: true })
    expect(wrapper.text()).toContain('组合风险上限--')
    expect(wrapper.text()).toContain('剩余风险容量未知--')
    expect(wrapper.text()).not.toContain('组合风险上限¥0.00')

    riskBudget = {
      ...riskBudget, status: 'incomplete', reason_code: 'portfolio_risk_coverage_incomplete',
      portfolio_equity: '100000', portfolio_limit_amount: '5000',
      covered_position_count: 1, open_position_count: 2,
    }
    await wrapper.findAll('button').find(button => button.text() === '刷新').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('存在无法计算止损风险的活动持仓')
    expect(wrapper.text()).toContain('查看未覆盖仓位')
    expect(wrapper.text()).toContain('剩余风险容量未知')
  })

  it('Settings 在能力发现失败时默认关闭风险政策并只保存监控设置', async () => {
    const { wrapper } = await mountAt(Settings, '/settings', [], 'error')
    expect(wrapper.text()).not.toContain('风险预算')
    await wrapper.findAll('button').find(button => button.text() === '保存并应用').trigger('click')
    await flushPromises()
    expect(api.put).toHaveBeenCalledWith('/settings', { poll_interval: 30, monitor_interval: 5 })
  })

  it('Settings 为 DeepSeek 提供不回显的配置、检测和清除操作', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/settings') return Promise.resolve({ data: {
        poll_interval: 30, monitor_interval: 5, deepseek_api_key_configured: false,
      } })
      return Promise.resolve({ data: {} })
    })
    api.put.mockResolvedValue({ data: {
      poll_interval: 30, monitor_interval: 5, deepseek_api_key_configured: true,
    } })
    api.post.mockResolvedValue({ data: {
      provider: 'deepseek', model: 'deepseek-v4-flash', status: 'ok',
    } })
    const { wrapper } = await mountAt(Settings, '/settings', [], { ai_holding_reviews: true })
    expect(wrapper.text()).toContain('DeepSeek 持仓复盘')
    expect(wrapper.text()).toContain('目标持仓的近期行情')
    await wrapper.get('input[aria-label="DeepSeek API Key"]').setValue('sk-component-test-secret')
    await wrapper.findAll('button').find(button => button.text() === '保存 DeepSeek Key').trigger('click')
    await flushPromises()
    expect(api.put).toHaveBeenCalledWith('/settings', { deepseek_api_key: 'sk-component-test-secret' })
    expect(wrapper.text()).toContain('已配置')
    await wrapper.findAll('button').find(button => button.text() === '检测连接').trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenCalledWith('/ai/deepseek/test', undefined, expect.any(Object))
  })

  it('HoldingDetail 触发状态提供重新布防并走 rearm 端点', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/holdings/12') return Promise.resolve({ data: { ...holdingData, status: 'triggered' } })
      if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
      return Promise.resolve({ data: {} })
    })
    api.post.mockResolvedValue({ data: {} })
    const { wrapper } = await mountAt(HoldingDetail, '/holdings/:id')
    const rearmButton = wrapper.findAll('button').find((button) => button.text() === '重新布防')
    expect(rearmButton).toBeTruthy()
    expect(wrapper.text()).toContain('该持仓已触发止损')

    await rearmButton.trigger('click')
    await flushPromises()
    const saveButton = wrapper.findAll('button').find((button) => button.text() === '保存修改')
    expect(saveButton).toBeTruthy()
    await saveButton.trigger('click')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/holdings/12/rearm', expect.objectContaining({
      stop_loss_method: 'fixed',
      stop_loss_value: 9,
    }))
    expect(api.put.mock.calls.some(([path]) => path === '/holdings/12')).toBe(false)
  })

  it('HoldingDetail 展示止损调整记录时间线', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/holdings/12') return Promise.resolve({ data: holdingData })
      if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
      if (path === '/holdings/12/stop-history') return Promise.resolve({ data: { items: [
        { id: 2, stop_loss_method: 'percentage', stop_loss_value: 10, stop_loss_price: 9, source: 'update', changed_at: '2026-07-30T06:00:00Z' },
        { id: 1, stop_loss_method: 'fixed', stop_loss_value: 9, stop_loss_price: 9, source: 'create', changed_at: '2026-07-24T08:00:00Z' },
      ] } })
      return Promise.resolve({ data: {} })
    })
    const { wrapper } = await mountAt(HoldingDetail, '/holdings/:id')
    expect(wrapper.text()).toContain('止损调整记录')
    expect(wrapper.text()).toContain('创建')
    expect(wrapper.text()).toContain('调整')
    expect(wrapper.text()).toContain('百分比 10%')
    expect(wrapper.text()).toContain('固定价格 9 元')
    expect(wrapper.text()).toContain('止损价 ¥9.00')
  })

  it('HoldingDetail 止损历史为空或加载失败时降级且不崩溃', async () => {
    const { wrapper } = await mountAt(HoldingDetail, '/holdings/:id')
    expect(wrapper.text()).toContain('暂无止损调整记录')

    api.get.mockImplementation((path) => {
      if (path === '/holdings/12') return Promise.resolve({ data: holdingData })
      if (path === '/holdings/12/stop-history') return Promise.reject(new Error('offline'))
      return Promise.resolve({ data: {} })
    })
    const { wrapper: failed } = await mountAt(HoldingDetail, '/holdings/:id')
    expect(failed.text()).toContain('无法加载止损调整记录')
    expect(failed.text()).toContain('权威持仓')
  })

  it('HoldingDetail 未配置 DeepSeek 时引导设置且不请求复盘', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/holdings/12') return Promise.resolve({ data: holdingData })
      if (path === '/settings') return Promise.resolve({ data: {
        poll_interval: 30, monitor_interval: 5, deepseek_api_key_configured: false,
      } })
      return Promise.resolve({ data: {} })
    })
    const { wrapper, router } = await mountAt(
      HoldingDetail,
      '/holdings/:id',
      [{ path: '/settings', component: { template: '<p>设置</p>' } }],
      { ai_holding_reviews: true },
    )
    expect(wrapper.text()).toContain('配置 DeepSeek 后可复盘')
    await wrapper.findAll('button').find(button => button.text() === '前往设置').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/settings')
    expect(api.post.mock.calls.some(([path]) => path.includes('/review'))).toBe(false)
  })

  it('HoldingDetail 按顺序刷新行情并展示结构化 AI 复盘', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/holdings/12') return Promise.resolve({ data: holdingData })
      if (path === '/settings') return Promise.resolve({ data: {
        poll_interval: 30, monitor_interval: 5, deepseek_api_key_configured: true,
      } })
      return Promise.resolve({ data: {} })
    })
    api.post.mockImplementation((path) => {
      if (path === '/ai/holdings/12/review') return Promise.resolve({ data: aiReviewData })
      return Promise.resolve({ data: {} })
    })
    const { wrapper, router } = await mountAt(
      HoldingDetail,
      '/holdings/:id',
      [{ path: '/planner', component: { template: '<p>风险试算</p>' } }],
      { ai_holding_reviews: true, risk_plan_previews: true },
    )
    const button = wrapper.findAll('button').find(item => item.text() === '更新行情并 AI 复盘')
    expect(button).toBeTruthy()
    await button.trigger('click')
    await flushPromises()
    expect(requestPriceRefresh).toHaveBeenCalledWith({ holding_id: '12' })
    expect(api.post).toHaveBeenCalledWith('/ai/holdings/12/review', undefined, expect.any(Object))
    expect(wrapper.text()).toContain('近期行情与风险保持可控。')
    expect(wrapper.text()).toContain('风险容量仍为正。')
    expect(wrapper.text()).toContain('不包含新闻、财报和未来价格预测')
    expect(wrapper.text()).toContain('DeepSeek · deepseek-v4-flash')
    const planner = wrapper.findAll('button').find(item => item.text() === '进入加仓风险试算')
    await planner.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/planner')
  })

  it('HoldingDetail 在能力晚到后显示配置引导', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/holdings/12') return Promise.resolve({ data: holdingData })
      if (path === '/settings') return Promise.resolve({ data: {
        poll_interval: 30, monitor_interval: 5, deepseek_api_key_configured: false,
      } })
      return Promise.resolve({ data: {} })
    })
    const { wrapper, pinia } = await mountAt(HoldingDetail, '/holdings/:id')
    expect(wrapper.text()).not.toContain('AI 持仓复盘')

    useRuntimeCapabilitiesStore(pinia).apply({
      authority_stage: 'legacy', stable_runtime_supported: true,
      capabilities: { ai_holding_reviews: true },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('AI 持仓复盘')
    expect(wrapper.text()).toContain('配置 DeepSeek 后可复盘')
  })

  it('HoldingDetail 展示三个阶段并阻止重复提交', async () => {
    const refresh = deferred()
    const reload = deferred()
    const review = deferred()
    let holdingLoads = 0
    api.get.mockImplementation((path) => {
      if (path === '/holdings/12') {
        holdingLoads += 1
        return holdingLoads === 1 ? Promise.resolve({ data: holdingData }) : reload.promise
      }
      if (path === '/settings') return Promise.resolve({ data: {
        poll_interval: 30, monitor_interval: 5, deepseek_api_key_configured: true,
      } })
      return Promise.resolve({ data: {} })
    })
    requestPriceRefresh.mockReturnValue(refresh.promise)
    api.post.mockImplementation((path) => (
      path === '/ai/holdings/12/review' ? review.promise : Promise.resolve({ data: {} })
    ))
    const { wrapper } = await mountAt(
      HoldingDetail, '/holdings/:id', [], { ai_holding_reviews: true },
    )
    const button = wrapper.findAll('button').find(item => item.text() === '更新行情并 AI 复盘')

    await button.trigger('click')
    await button.trigger('click')
    expect(requestPriceRefresh).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('.ai-progress li')[0].classes()).toContain('active')

    refresh.resolve({ data: {} })
    await flushPromises()
    expect(wrapper.findAll('.ai-progress li')[1].classes()).toContain('active')

    reload.resolve({ data: holdingData })
    await flushPromises()
    expect(wrapper.findAll('.ai-progress li')[2].classes()).toContain('active')
    expect(api.post.mock.calls.filter(([path]) => path.includes('/review'))).toHaveLength(1)

    review.resolve({ data: aiReviewData })
    await flushPromises()
    expect(wrapper.text()).toContain('近期行情与风险保持可控。')
  })

  it('HoldingDetail 在超时后可重试且保留核心持仓操作', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/holdings/12') return Promise.resolve({ data: holdingData })
      if (path === '/settings') return Promise.resolve({ data: {
        poll_interval: 30, monitor_interval: 5, deepseek_api_key_configured: true,
      } })
      return Promise.resolve({ data: {} })
    })
    requestPriceRefresh.mockResolvedValue({ data: {} })
    api.post
      .mockRejectedValueOnce({ response: { data: { detail: { error_code: 'ai_timeout' } } } })
      .mockResolvedValueOnce({ data: aiReviewData })
    const { wrapper } = await mountAt(
      HoldingDetail, '/holdings/:id', [], { ai_holding_reviews: true },
    )

    await wrapper.findAll('button').find(item => item.text() === '更新行情并 AI 复盘').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('DeepSeek 响应超时')
    expect(wrapper.text()).toContain('修改止损')
    expect(wrapper.text()).toContain('手动平仓')

    await wrapper.findAll('button').find(item => item.text() === '重新复盘').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('近期行情与风险保持可控。')
  })

  it('HoldingDetail 突出已触发止损且离开页面后不保留复盘', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/holdings/12') return Promise.resolve({ data: { ...holdingData, status: 'triggered' } })
      if (path === '/settings') return Promise.resolve({ data: {
        poll_interval: 30, monitor_interval: 5, deepseek_api_key_configured: true,
      } })
      return Promise.resolve({ data: {} })
    })
    requestPriceRefresh.mockResolvedValue({ data: {} })
    api.post.mockResolvedValue({ data: {
      ...aiReviewData, summary: '止损已触发，应按既定计划处置。',
      action: 'execute_existing_stop', can_open_add_on_preview: false,
    } })
    const first = await mountAt(
      HoldingDetail, '/holdings/:id', [],
      { ai_holding_reviews: true, risk_plan_previews: true },
    )
    await first.wrapper.findAll('button').find(item => item.text() === '更新行情并 AI 复盘').trigger('click')
    await flushPromises()
    expect(first.wrapper.text()).toContain('执行既定止损')
    expect(first.wrapper.text()).not.toContain('进入加仓风险试算')
    first.wrapper.unmount()

    const second = await mountAt(
      HoldingDetail, '/holdings/:id', [],
      { ai_holding_reviews: true, risk_plan_previews: true },
    )
    expect(second.wrapper.text()).not.toContain('止损已触发，应按既定计划处置。')
  })

  it('HoldingDetail 在风险试算能力关闭时隐藏 AI 加仓入口', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/holdings/12') return Promise.resolve({ data: holdingData })
      if (path === '/settings') return Promise.resolve({ data: {
        poll_interval: 30, monitor_interval: 5, deepseek_api_key_configured: true,
      } })
      return Promise.resolve({ data: {} })
    })
    requestPriceRefresh.mockResolvedValue({ data: {} })
    api.post.mockResolvedValue({ data: aiReviewData })
    const { wrapper } = await mountAt(
      HoldingDetail, '/holdings/:id', [],
      { ai_holding_reviews: true, risk_plan_previews: false },
    )
    await wrapper.findAll('button').find(item => item.text() === '更新行情并 AI 复盘').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('可进一步试算加仓风险')
    expect(wrapper.text()).not.toContain('进入加仓风险试算')
    expect(wrapper.text()).toContain('复盘不是收益预测或交易指令')
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

  it('Dashboard 展示待处置持仓队列且无触发时不渲染', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
      if (path === '/dashboard') return Promise.resolve({ data: {
        ...dashboardData, triggered_count: 1,
        holdings: [{ ...dashboardData.holdings[0], status: 'triggered' }],
      } })
      if (path === '/monitoring/status') return Promise.resolve({ data: { scheduler_running: true, overdue: false, quote_coverage_pct: 100 } })
      return Promise.resolve({ data: {} })
    })
    const { wrapper, router } = await mountAt(Dashboard, '/', [
      { path: '/holdings/:id', component: { template: '<p>持仓详情</p>' } },
    ])
    expect(wrapper.text()).toContain('待处置持仓')
    const goButton = wrapper.findAll('button').find((button) => button.text() === '去处置')
    expect(goButton).toBeTruthy()
    await goButton.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/holdings/12')

    api.get.mockImplementation((path) => {
      if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
      if (path === '/dashboard') return Promise.resolve({ data: dashboardData })
      if (path === '/monitoring/status') return Promise.resolve({ data: { scheduler_running: true, overdue: false, quote_coverage_pct: 100 } })
      return Promise.resolve({ data: {} })
    })
    const { wrapper: clean } = await mountAt(Dashboard, '/')
    expect(clean.text()).not.toContain('待处置持仓')
  })

  it('Dashboard 展示交易时段徽标且状态缺失时降级', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
      if (path === '/dashboard') return Promise.resolve({ data: dashboardData })
      if (path === '/monitoring/status') return Promise.resolve({ data: { scheduler_running: true, overdue: false, quote_coverage_pct: 100, market_session: 'open' } })
      return Promise.resolve({ data: {} })
    })
    const { wrapper } = await mountAt(Dashboard, '/')
    expect(wrapper.text()).toContain('交易中')

    api.get.mockImplementation((path) => {
      if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
      if (path === '/dashboard') return Promise.resolve({ data: dashboardData })
      if (path === '/monitoring/status') return Promise.resolve({ data: { scheduler_running: true, overdue: false, quote_coverage_pct: 100 } })
      return Promise.resolve({ data: {} })
    })
    const { wrapper: degraded } = await mountAt(Dashboard, '/')
    expect(degraded.text()).not.toContain('交易中')
    expect(degraded.text()).toContain('权威持仓')
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
