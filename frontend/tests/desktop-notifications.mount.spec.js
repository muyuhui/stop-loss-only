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

function FakeNotification() {
  throw new Error('设置页测试中不应真正创建系统通知')
}
FakeNotification.permission = 'granted'
FakeNotification.requestPermission = vi.fn(async () => 'granted')

const stubs = {
  DataState: { props: ['title'], template: '<div>{{ title }}</div>' },
  ElButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
  ElTag: { template: '<span><slot /></span>' },
  ElSwitch: {
    props: ['modelValue', 'loading'],
    emits: ['update:modelValue', 'change'],
    template: '<button type="button" role="switch" :aria-checked="modelValue" @click="$emit(\'update:modelValue\', !modelValue); $emit(\'change\', !modelValue)"><slot /></button>',
  },
  ElRadioGroup: {
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
    template: '<div role="radiogroup"><slot /></div>',
  },
  ElRadioButton: {
    props: ['value', 'label'],
    template: '<span><slot /></span>',
  },
}

function settingsPayload(overrides = {}) {
  return {
    poll_interval: 30, monitor_interval: 5,
    webhook_enabled: false, webhook_target_configured: false, webhook_secret_configured: false,
    webhook_payload_level: 'minimal', quote_retention_days: 90, diagnostics_retention_days: 30,
    import_max_bytes: 1048576, import_max_rows: 1000,
    portfolio_equity: null, portfolio_risk_limit_pct: '5', default_position_risk_limit_pct: '1',
    portfolio_equity_updated_at: null, deepseek_api_key_configured: false,
    desktop_notifications_enabled: false, desktop_notification_mode: 'full', desktop_notifications_paused: false,
    ...overrides,
  }
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
  localStorage.clear()
  window.Notification = FakeNotification
  vi.mocked(api.get).mockResolvedValue({ data: settingsPayload() })
  vi.mocked(api.put).mockImplementation(async (url, body) => ({ data: settingsPayload(body) }))
})

afterEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

describe('桌面通知设置区', () => {
  it('能力开启时渲染三个控件', async () => {
    const wrapper = await mountSettings({ browser_notifications: true, desktop_notifications: true })
    expect(wrapper.text()).toContain('桌面通知（本地）')
    expect(wrapper.find('[aria-label="桌面通知开关"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('完整')
    expect(wrapper.text()).toContain('脱敏')
    expect(wrapper.find('[aria-label="演示模式开关"]').exists()).toBe(true)
  })

  it('能力关闭时不渲染桌面通知区', async () => {
    const wrapper = await mountSettings({})
    expect(wrapper.text()).not.toContain('桌面通知（本地）')
  })

  it('开启桌面通知提交三键', async () => {
    const wrapper = await mountSettings({ browser_notifications: true, desktop_notifications: true })
    await wrapper.find('[aria-label="桌面通知开关"]').trigger('click')
    await flushPromises()
    expect(api.put).toHaveBeenCalledWith('/settings', {
      desktop_notifications_enabled: true,
      desktop_notification_mode: 'full',
      desktop_notifications_paused: false,
    })
  })

  it('选择脱敏模式提交 redacted', async () => {
    const wrapper = await mountSettings({ browser_notifications: true, desktop_notifications: true })
    const group = wrapper.findComponent(stubs.ElRadioGroup)
    group.vm.$emit('update:modelValue', 'redacted')
    group.vm.$emit('change', 'redacted')
    await flushPromises()
    expect(api.put).toHaveBeenCalledWith('/settings', {
      desktop_notifications_enabled: false,
      desktop_notification_mode: 'redacted',
      desktop_notifications_paused: false,
    })
  })

  it('开启演示模式提交 paused', async () => {
    const wrapper = await mountSettings({ browser_notifications: true, desktop_notifications: true })
    await wrapper.find('[aria-label="演示模式开关"]').trigger('click')
    await flushPromises()
    expect(api.put).toHaveBeenCalledWith('/settings', {
      desktop_notifications_enabled: false,
      desktop_notification_mode: 'full',
      desktop_notifications_paused: true,
    })
  })

  it('加载时回填后端设置', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: settingsPayload({
      desktop_notifications_enabled: true, desktop_notification_mode: 'redacted', desktop_notifications_paused: true,
    }) })
    const wrapper = await mountSettings({ browser_notifications: true, desktop_notifications: true })
    expect(wrapper.find('[aria-label="桌面通知开关"]').attributes('aria-checked')).toBe('true')
    expect(wrapper.find('[aria-label="演示模式开关"]').attributes('aria-checked')).toBe('true')
  })
})
