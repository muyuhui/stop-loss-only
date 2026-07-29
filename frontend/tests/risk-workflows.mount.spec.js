import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../src/api'
import Holdings from '../src/views/Holdings.vue'

vi.mock('../src/api', () => ({ default: { get: vi.fn() } }))

const stubs = {
  ElButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
  ElDialog: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' },
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: { template: '<div />' },
  ElPagination: true,
  ElTag: { template: '<span><slot /></span>' },
  HoldingForm: { emits: ['success', 'cancel'], template: '<button class="holding-form-success" @click="$emit(\'success\')">save</button>' },
}

async function mountHoldings() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/holdings', component: Holdings }, { path: '/holdings/:id', component: { template: '<p>detail</p>' } }],
  })
  await router.push('/holdings')
  await router.isReady()
  return mount(Holdings, { global: { plugins: [router], stubs } })
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
    const wrapper = await mountHoldings()
    await flushPromises()
    await wrapper.get('.page-heading button').trigger('click')
    await wrapper.get('.holding-form-success').trigger('click')
    await flushPromises()
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('does not expose the unfinished position-domain interface in the legacy route', async () => {
    const wrapper = await mountHoldings()
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
    const wrapper = await mountHoldings()
    await flushPromises()
    expect(wrapper.text()).toContain('待取价持仓')
    expect(wrapper.text()).toContain('未定价')
    expect(wrapper.text()).toContain('风险未知')
    expect(wrapper.text()).not.toContain('0.00%')
  })
})
