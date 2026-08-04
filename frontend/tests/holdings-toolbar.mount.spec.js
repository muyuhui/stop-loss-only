import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../src/api'
import { HOLDINGS_SORT_KEY } from '../src/utils/holdingsQuery'
import Holdings from '../src/views/Holdings.vue'

vi.mock('../src/api', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

const stubs = {
  DataState: { props: ['title'], template: '<div>{{ title }}</div>' },
  HoldingForm: true,
  ElButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
  ElInput: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElSelect: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
  },
  ElOption: { props: ['value', 'label'], template: '<option :value="value">{{ label }}</option>' },
  ElDialog: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' },
}

async function mountHoldings() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/holdings', component: Holdings },
      { path: '/holdings/:id', component: { template: '<div />' } },
    ],
  })
  await router.push('/holdings')
  await router.isReady()
  const wrapper = mount(Holdings, { global: { plugins: [createPinia(), router], stubs } })
  await flushPromises()
  return wrapper
}

function lastParams() {
  const call = vi.mocked(api.get).mock.calls.at(-1)
  return call ? call[1]?.params : undefined
}

beforeEach(() => {
  localStorage.clear()
  vi.mocked(api.get).mockResolvedValue({ data: { items: [], total: 0 } })
})

afterEach(() => {
  vi.mocked(api.get).mockReset()
  localStorage.clear()
})

describe('持仓工具栏', () => {
  it('首次加载使用默认排序且不携带筛选', async () => {
    await mountHoldings()
    expect(lastParams()).toEqual({ page: 1, size: 20 })
  })

  it('输入搜索词触发带 page 1 的查询', async () => {
    const wrapper = await mountHoldings()
    await wrapper.get('input[placeholder="搜索名称或代码"]').setValue('银行')
    await flushPromises()
    expect(lastParams()).toEqual({ page: 1, size: 20, search: '银行' })
  })

  it('切换状态与类型筛选触发刷新', async () => {
    const wrapper = await mountHoldings()
    const selects = wrapper.findAll('select')
    await selects[0].setValue('holding')
    await flushPromises()
    expect(lastParams()).toEqual({ page: 1, size: 20, status: 'holding' })
    await selects[1].setValue('fund')
    await flushPromises()
    expect(lastParams()).toEqual({ page: 1, size: 20, status: 'holding', type: 'fund' })
  })

  it('选择排序写入 localStorage 并请求', async () => {
    const wrapper = await mountHoldings()
    await wrapper.findAll('select')[2].setValue('risk')
    await flushPromises()
    expect(lastParams()).toEqual({ page: 1, size: 20, sort: 'risk' })
    expect(localStorage.getItem(HOLDINGS_SORT_KEY)).toBe('risk')
  })

  it('重置恢复默认筛选与排序', async () => {
    const wrapper = await mountHoldings()
    await wrapper.get('input[placeholder="搜索名称或代码"]').setValue('银行')
    await wrapper.findAll('select')[2].setValue('risk')
    await flushPromises()
    await wrapper.findAll('button').filter((button) => button.text() === '重置')[0].trigger('click')
    await flushPromises()
    expect(lastParams()).toEqual({ page: 1, size: 20 })
    expect(localStorage.getItem(HOLDINGS_SORT_KEY)).toBe('newest')
  })

  it('进入页面时恢复已保存的排序', async () => {
    localStorage.setItem(HOLDINGS_SORT_KEY, 'risk')
    await mountHoldings()
    expect(lastParams()).toEqual({ page: 1, size: 20, sort: 'risk' })
  })

  it('存储脏值回退默认排序', async () => {
    localStorage.setItem(HOLDINGS_SORT_KEY, 'profit')
    await mountHoldings()
    expect(lastParams()).toEqual({ page: 1, size: 20 })
  })
})
