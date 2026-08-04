import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../src/api'
import HoldingForm from '../src/components/HoldingForm.vue'
import Holdings from '../src/views/Holdings.vue'
import { useRuntimeCapabilitiesStore } from '../src/stores/runtimeCapabilities'

vi.mock('../src/api', () => ({ default: { get: vi.fn() } }))

const stubs = {
  ElButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
  ElDialog: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' },
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: { template: '<div />' },
  ElPagination: true,
  ElTag: { template: '<span><slot /></span>' },
  HoldingForm: {
    props: ['initialValues'], emits: ['success', 'cancel'],
    template: '<div><button class="holding-form-success" @click="$emit(\'success\')">save</button><button class="holding-form-cancel" @click="$emit(\'cancel\')">cancel</button><span class="prefill-code">{{ initialValues?.code }}</span></div>',
  },
}

async function mountHoldings(path = '/holdings', capabilities = null) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/holdings', component: Holdings }, { path: '/holdings/:id', component: { template: '<p>detail</p>' } }],
  })
  await router.push(path)
  await router.isReady()
  const pinia = createPinia()
  if (capabilities) {
    useRuntimeCapabilitiesStore(pinia).apply({
      authority_stage: 'legacy', stable_runtime_supported: true, capabilities,
    })
  }
  const wrapper = mount(Holdings, { global: { plugins: [pinia, router], stubs } })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  api.get.mockResolvedValue({ data: { items: [], total: 0 } })
  vi.clearAllMocks()
})

describe('legacy holdings page', () => {
  it('loads the authoritative legacy holdings endpoint', async () => {
    await mountHoldings()
    await flushPromises()
    expect(api.get).toHaveBeenCalledWith('/holdings', { params: { page: 1, size: 20 } })
  })

  it('opens the existing holding form and reloads after a save', async () => {
    const { wrapper } = await mountHoldings()
    await flushPromises()
    await wrapper.get('.page-heading button').trigger('click')
    await wrapper.get('.holding-form-success').trigger('click')
    await flushPromises()
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('does not expose the unfinished position-domain interface in the legacy route', async () => {
    const { wrapper } = await mountHoldings()
    await flushPromises()
    expect(wrapper.text()).toContain('持仓管理')
    expect(wrapper.text()).toContain('新增持仓')
    expect(wrapper.text()).not.toContain('新建仓位')
  })

  it('renders an unpriced holding without fabricated zero risk', async () => {
    api.get.mockResolvedValue({ data: { items: [{
      id: 1, code: '000001', name: '待取价持仓', type: 'stock', quantity: 100,
      buy_price: 10, current_price: null, stop_loss_price: 9, stop_loss_method: 'fixed',
      profit_loss_pct: null, stop_loss_distance_pct: null, quote_state: 'unpriced', status: 'holding',
    }], total: 1 } })
    const { wrapper } = await mountHoldings()
    await flushPromises()
    expect(wrapper.text()).toContain('待取价持仓')
    expect(wrapper.text()).toContain('未定价')
    expect(wrapper.text()).toContain('风险未知')
    expect(wrapper.text()).not.toContain('0.00%')
  })

  it('从试算预填参数自动打开新增表单并在取消后清理路由', async () => {
    const { wrapper, router } = await mountHoldings(
      '/holdings?create=1&code=000001&name=甲&type=stock&buy_price=20&quantity=400&stop_method=fixed&stop_value=18&buy_date=2026-08-04',
    )
    expect(wrapper.get('.prefill-code').text()).toBe('000001')
    expect(wrapper.findComponent(HoldingForm).props('initialValues')).toMatchObject({
      code: '000001', name: '甲', type: 'stock', buy_price: 20, quantity: 400,
      stop_loss_method: 'fixed', stop_loss_value: 18, buy_date: '2026-08-04',
    })
    await wrapper.get('.holding-form-cancel').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({})
    expect(wrapper.findComponent(HoldingForm).exists()).toBe(false)
  })

  it('预填表单保存成功后清理 create 参数', async () => {
    const { wrapper, router } = await mountHoldings(
      '/holdings?create=1&code=000001&name=甲&type=stock&buy_price=20&quantity=400&stop_method=fixed&stop_value=18&buy_date=2026-08-04',
    )
    await wrapper.get('.holding-form-success').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({})
  })

  it('非法或缺失的预填参数被静默忽略', async () => {
    const { wrapper } = await mountHoldings(
      '/holdings?create=1&code=&name=甲&type=stock&buy_price=20&quantity=400&stop_method=fixed&stop_value=18',
    )
    expect(wrapper.findComponent(HoldingForm).exists()).toBe(false)
    expect(api.get).toHaveBeenCalledWith('/holdings', expect.anything())
  })

  it('legacy_holding_writes 不可用时忽略预填参数', async () => {
    const { wrapper } = await mountHoldings(
      '/holdings?create=1&code=000001&name=甲&type=stock&buy_price=20&quantity=400&stop_method=fixed&stop_value=18&buy_date=2026-08-04',
      { legacy_holding_writes: false },
    )
    expect(wrapper.findComponent(HoldingForm).exists()).toBe(false)
  })
})
