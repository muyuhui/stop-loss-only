import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../src/api'
import Settings from '../src/views/Settings.vue'
import { useRuntimeCapabilitiesStore } from '../src/stores/runtimeCapabilities'

vi.mock('../src/api', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() },
  requestHoldingHistory: vi.fn(),
  requestPriceRefresh: vi.fn(),
  refreshErrorMessage: vi.fn(() => '价格刷新失败，请稍后重试。'),
}))

function makeNotification(permission, requestResult) {
  function FakeNotification() {
    throw new Error('设置页测试中不应真正创建系统通知')
  }
  FakeNotification.permission = permission
  FakeNotification.requestPermission = vi.fn(async () => requestResult ?? permission)
  return FakeNotification
}

const stubs = {
  DataState: { props: ['title'], template: '<div>{{ title }}</div>' },
  ElButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
  ElTag: { template: '<span><slot /></span>' },
  ElInputNumber: true,
  ElInput: {
    props: ['modelValue'], emits: ['update:modelValue'],
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElSwitch: {
    props: ['modelValue', 'loading'],
    emits: ['change'],
    template: '<button type="button" role="switch" :aria-checked="modelValue" @click="$emit(\'change\', !modelValue)"><slot /></button>',
  },
}

async function mountSettings(capabilities) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/settings', component: Settings }],
  })
  await router.push('/settings')
  await router.isReady()
  const pinia = createPinia()
  useRuntimeCapabilitiesStore(pinia).apply({
    authority_stage: 'legacy', stable_runtime_supported: true, capabilities,
  })
  const wrapper = mount(Settings, { global: { plugins: [pinia, router], stubs } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockImplementation((path) => {
    if (path === '/settings') return Promise.resolve({ data: { poll_interval: 30, monitor_interval: 5 } })
    if (path === '/monitoring/status') return Promise.resolve({ data: { scheduler_running: true, overdue: false } })
    return Promise.resolve({ data: {} })
  })
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('触发通知设置区', () => {
  it('开启通知开关时才请求权限，授权后开关保持开启', async () => {
    vi.stubGlobal('Notification', makeNotification('default', 'granted'))
    const wrapper = await mountSettings({ browser_notifications: true })
    expect(wrapper.text()).toContain('触发通知')
    const notificationSwitch = wrapper.findAll('[role="switch"]')
      .find((item) => item.attributes('aria-label') === '系统通知开关')
    expect(notificationSwitch.attributes('aria-checked')).toBe('false')

    await notificationSwitch.trigger('click')
    await flushPromises()

    expect(Notification.requestPermission).toHaveBeenCalledTimes(1)
    expect(notificationSwitch.attributes('aria-checked')).toBe('true')
    expect(wrapper.text()).toContain('已授予')
  })

  it('权限已拒绝时不再请求、开关保持关闭并显示重新授权指引且不崩溃', async () => {
    vi.stubGlobal('Notification', makeNotification('denied'))
    const wrapper = await mountSettings({ browser_notifications: true })
    const notificationSwitch = wrapper.findAll('[role="switch"]')
      .find((item) => item.attributes('aria-label') === '系统通知开关')

    await notificationSwitch.trigger('click')
    await flushPromises()

    expect(Notification.requestPermission).not.toHaveBeenCalled()
    expect(notificationSwitch.attributes('aria-checked')).toBe('false')
    expect(wrapper.text()).toContain('被拒绝')
    expect(wrapper.text()).toContain('浏览器站点设置')
  })

  it('能力不可用时整个通知区不渲染', async () => {
    const wrapper = await mountSettings({})
    expect(wrapper.text()).not.toContain('触发通知')
    expect(wrapper.text()).not.toContain('系统通知开关')
    expect(wrapper.text()).not.toContain('提示音开关')
  })

  it('声音开关独立于通知开关且默认关闭', async () => {
    vi.stubGlobal('Notification', makeNotification('granted'))
    const wrapper = await mountSettings({ browser_notifications: true })
    const soundSwitch = wrapper.findAll('[role="switch"]')
      .find((item) => item.attributes('aria-label') === '提示音开关')
    expect(soundSwitch.attributes('aria-checked')).toBe('false')

    await soundSwitch.trigger('click')

    expect(soundSwitch.attributes('aria-checked')).toBe('true')
  })
})
