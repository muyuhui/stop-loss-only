import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../src/api'
import Alerts from '../src/views/Alerts.vue'

vi.mock('../src/api', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}))

const alertItem = {
  id: 7, holding_id: 12, position_id: 34, holding_name: '测试持仓', holding_code: '000001',
  current_price: 8, trigger_price: 9, read: false, disposition: 'triggered',
}

const stubs = {
  DataState: {
    props: ['title', 'description', 'actionLabel'], emits: ['action'],
    template: '<div><strong>{{ title }}</strong><span>{{ description }}</span><button v-if="actionLabel" @click="$emit(\'action\')">{{ actionLabel }}</button></div>',
  },
  ElButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
  ElInput: {
    inheritAttrs: false, props: ['modelValue'], emits: ['update:modelValue', 'keyup', 'clear'],
    template: '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" @keyup.enter="$emit(\'keyup\', $event)" />',
  },
  ElSelect: {
    inheritAttrs: false, props: ['modelValue'], emits: ['update:modelValue', 'change'],
    template: '<select v-bind="$attrs" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value); $emit(\'change\', $event.target.value)"><slot /></select>',
  },
  ElOption: { props: ['label', 'value'], template: '<option :value="value">{{ label }}</option>' },
  ElTag: { template: '<span><slot /></span>' },
  ElPagination: { emits: ['currentChange'], template: '<button class="next-page" @click="$emit(\'currentChange\', 2)">下一页</button>' },
}

async function mountAlerts(initialPath = '/alerts') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/alerts', component: Alerts },
      { path: '/holdings/:id', component: { template: '<p>持仓详情</p>' } },
    ],
  })
  await router.push(initialPath)
  await router.isReady()
  const wrapper = mount(Alerts, { global: { plugins: [createPinia(), router], stubs } })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockResolvedValue({ data: { items: [alertItem], total: 21 } })
  api.put.mockResolvedValue({ data: { ok: true } })
})

describe('告警稳定路由', () => {
  it('只显示服务端支持的中文筛选，并将搜索和分页写入 URL 与请求', async () => {
    const { wrapper, router } = await mountAlerts('/alerts?search=平安&unread=false&disposition=closed&page=2')
    expect(api.get).toHaveBeenCalledWith('/alerts', { params: {
      search: '平安', page: 2, size: 20, unread: 'false', disposition: 'closed',
    } })
    expect(wrapper.get('input[aria-label="搜索告警"]')).toBeTruthy()
    expect(wrapper.get('select[aria-label="阅读状态"]')).toBeTruthy()
    expect(wrapper.get('select[aria-label="处置状态"]')).toBeTruthy()
    expect(wrapper.text()).not.toMatch(/生命周期|风险筛选|最新优先|风险优先/)

    await wrapper.get('input[aria-label="搜索告警"]').setValue('招商')
    await wrapper.findAll('button').find(button => button.text() === '搜索').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.search).toBe('招商')
    expect(api.get).toHaveBeenLastCalledWith('/alerts', { params: {
      search: '招商', page: 1, size: 20, unread: 'false', disposition: 'closed',
    } })

    await wrapper.get('.next-page').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.page).toBe('2')
  })

  it('筛选为空时显示匹配空状态，重置后恢复无筛选 URL', async () => {
    api.get.mockResolvedValue({ data: { items: [], total: 0 } })
    const { wrapper, router } = await mountAlerts('/alerts?search=不存在')
    expect(wrapper.text()).toContain('没有匹配的告警')
    expect(wrapper.text()).not.toContain('还没有告警')
    await wrapper.findAll('button').find(button => button.text() === '重置筛选').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({})
  })

  it('同时存在 holding_id 和 position_id 时只进入已注册的持仓详情', async () => {
    const { wrapper, router } = await mountAlerts()
    const action = wrapper.findAll('button').find((button) => button.text().includes('去处置'))
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
