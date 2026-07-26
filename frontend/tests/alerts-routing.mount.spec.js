import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../src/api'
import Alerts from '../src/views/Alerts.vue'

vi.mock('../src/api', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}))

const stubs = {
  DataState: true,
  FilterToolbar: true,
  ElButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
  ElSelect: { template: '<select><slot /></select>' },
  ElOption: true,
  ElTag: { template: '<span><slot /></span>' },
  ElPagination: true,
}

async function mountAlerts() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/alerts', component: Alerts },
      { path: '/holdings/:id', component: { template: '<p>持仓详情</p>' } },
    ],
  })
  await router.push('/alerts')
  await router.isReady()
  const wrapper = mount(Alerts, { global: { plugins: [createPinia(), router], stubs } })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockImplementation((path) => Promise.resolve({
    data: path === '/alerts'
      ? { items: [{ id: 7, holding_id: 12, position_id: 34, holding_name: '测试持仓', holding_code: '000001', current_price: 8, trigger_price: 9, read: false }], total: 1 }
      : { items: [], total: 0 },
  }))
})

describe('告警稳定路由', () => {
  it('同时存在 holding_id 和 position_id 时只进入已注册的持仓详情', async () => {
    const { wrapper, router } = await mountAlerts()
    const action = wrapper.findAll('button').find((button) => button.text().includes('查看持仓'))
    expect(action).toBeTruthy()
    await action.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/holdings/12')
    expect(router.currentRoute.value.fullPath).not.toContain('/positions/')
  })

  it('告警页面可见命令不引用未注册 Position 路由', async () => {
    const { wrapper } = await mountAlerts()
    expect(wrapper.text()).not.toContain('Position')
    expect(wrapper.html()).not.toContain('/positions/')
  })
})
