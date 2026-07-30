import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../src/api'
import App from '../src/App.vue'

vi.mock('../src/api', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

const stubs = {
  ElBadge: { template: '<span><slot /></span>' },
  ElIcon: { template: '<span><slot /></span>' },
}

async function mountShell(capabilityResponse) {
  api.get.mockImplementation((path) => {
    if (path === '/runtime/capabilities') return capabilityResponse
    if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
    if (path === '/alerts?unread=true&size=1') return Promise.resolve({ data: { items: [] } })
    if (path === '/alerts/count') return Promise.resolve({ data: { count: 0 } })
    return Promise.resolve({ data: {} })
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<p>核心页面</p>' } },
      { path: '/planner', component: { template: '<p>规划器</p>' } },
      { path: '/holdings', component: { template: '<p>持仓</p>' } },
      { path: '/alerts', component: { template: '<p>告警</p>' } },
      { path: '/settings', component: { template: '<p>设置</p>' } },
    ],
  })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [createPinia(), router], stubs } })
  await flushPromises()
  return wrapper
}

beforeEach(() => vi.clearAllMocks())
afterEach(() => vi.restoreAllMocks())

describe('runtime capability shell', () => {
  it('shows risk preview navigation for the stable legacy runtime', async () => {
    const wrapper = await mountShell(Promise.resolve({ data: {
      authority_stage: 'legacy',
      stable_runtime_supported: true,
      capabilities: { legacy_holding_writes: true, risk_plan_previews: true },
    } }))

    expect(wrapper.text()).toContain('核心页面')
    expect(wrapper.text()).toContain('风险试算')
    wrapper.unmount()
  })

  it('fails optional navigation closed while preserving the core page', async () => {
    const wrapper = await mountShell(Promise.reject(new Error('offline')))

    expect(wrapper.text()).toContain('核心页面')
    expect(wrapper.text()).not.toContain('风险试算')
    wrapper.unmount()
  })

  it('shows planner navigation only when explicitly declared', async () => {
    const wrapper = await mountShell(Promise.resolve({ data: {
      authority_stage: 'new-authoritative',
      stable_runtime_supported: false,
      capabilities: { risk_plan_previews: true },
    } }))

    expect(wrapper.text()).toContain('风险试算')
    wrapper.unmount()
  })
})
