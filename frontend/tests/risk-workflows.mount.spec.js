import { defineComponent, h, nextTick, onMounted } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../src/api'
import Holdings from '../src/views/Holdings.vue'
import { createResource } from '../src/stores/resource'
import { createPoller } from '../src/utils/poller'

const mocked = vi.hoisted(() => ({ store: null }))

vi.mock('../src/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../src/stores/positions', () => ({ usePositionsStore: () => mocked.store }))

const stubs = {
  ElButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
  ElInput: { props: ['modelValue'], emits: ['update:modelValue'], template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
  ElSelect: { props: ['modelValue'], emits: ['update:modelValue'], template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>' },
  ElOption: { template: '<option><slot /></option>' },
  ElDialog: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' },
}

function row(id = 1) {
  return { id, name: 'Alpha', code: '600001', asset_type: 'stock', lifecycle_status: 'open', risk_status: 'normal', remaining_quantity: '10', current_price: '12.30', quote_state: 'fresh' }
}

async function mountHoldings(url = '/holdings') {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/holdings', component: Holdings }, { path: '/positions/:id', component: { template: '<p>detail</p>' } }] })
  await router.push(url); await router.isReady()
  return mount(Holdings, { global: { plugins: [router], stubs } })
}

beforeEach(() => {
  mocked.store = { data: null, error: null, loading: false, refresh: vi.fn().mockResolvedValue(undefined) }
  vi.clearAllMocks()
})

describe('risk workflow component mounts', () => {
  it('renders the initial loading state and preserves last success data on a background error', async () => {
    mocked.store.loading = true
    const loading = await mountHoldings()
    expect(loading.get('[data-state="loading"]').attributes('role')).toBe('status')

    mocked.store = { data: { items: [row()] }, error: new Error('offline'), loading: false, refresh: vi.fn().mockRejectedValue(new Error('offline')) }
    const stale = await mountHoldings()
    expect(stale.text()).toContain('Alpha')
    expect(stale.get('.status-banner').attributes('role')).toBe('status')
  })

  it('restores URL search context and validates then submits the create-position form', async () => {
    mocked.store = { data: { items: [row()] }, error: null, loading: false, refresh: vi.fn().mockResolvedValue(undefined) }
    api.post.mockResolvedValue({ data: row(9) })
    const wrapper = await mountHoldings('/holdings?search=Alpha&sort=name')
    await flushPromises()
    expect(wrapper.get('.filter-toolbar input').element.value).toBe('Alpha')

    await wrapper.get('.heading-actions button').trigger('click')
    await wrapper.get('form.create-form').trigger('submit')
    expect(wrapper.text()).toContain('无法创建仓位')

    const inputs = wrapper.findAll('form.create-form input')
    await inputs[0].setValue('600009'); await inputs[1].setValue('Test'); await inputs[2].setValue('100'); await inputs[3].setValue('9.50')
    await wrapper.get('form.create-form').trigger('submit')
    await flushPromises()
    expect(api.post).toHaveBeenCalledWith('/positions', expect.objectContaining({ code: '600009', name: 'Test', quantity: '100', unit_cost: '9.50' }))
  })

  it('keeps mounted resource data during a failed refresh and owns one timer per mounted resource', async () => {
    const loader = vi.fn().mockResolvedValueOnce('last success').mockRejectedValueOnce(new Error('offline'))
    const timerHost = { setInterval: vi.fn(() => 17), clearInterval: vi.fn() }
    const Harness = defineComponent({
      setup() {
        const resource = createResource(loader)
        const poller = createPoller(vi.fn(), timerHost, { visibilityState: 'visible' })
        onMounted(async () => { await resource.refresh(); poller.start(30); poller.start(30) })
        return { resource }
      },
      render() { return h('div', [h('button', { onClick: () => this.resource.refresh().catch(() => {}) }, 'refresh'), h('p', this.resource.data.value || 'none'), h('p', this.resource.error.value ? 'background error' : 'healthy')]) },
    })
    const wrapper = mount(Harness)
    await flushPromises()
    expect(wrapper.text()).toContain('last success')
    expect(timerHost.setInterval).toHaveBeenCalledTimes(2)
    expect(timerHost.clearInterval).toHaveBeenCalledTimes(1)
    await wrapper.get('button').trigger('click'); await flushPromises(); await nextTick()
    expect(wrapper.text()).toContain('last success')
    expect(wrapper.text()).toContain('background error')
  })
})
