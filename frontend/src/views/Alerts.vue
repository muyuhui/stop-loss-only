<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import DataState from '../components/DataState.vue'
import { useAlertStore } from '../stores/alert'
import { formatMoney, formatTime } from '../utils/format'
import { useRequestState } from '../utils/requestState'

const route = useRoute()
const router = useRouter()
const alerts = ref([])
const total = ref(0)
const marking = ref(false)
const request = useRequestState()
const alertStore = useAlertStore()
const query = reactive({ search: '', page: 1, unread: '', disposition: '' })
const hasFilters = computed(() => Boolean(query.search || query.unread || query.disposition))

function routeValue(name) {
  const value = route.query[name]
  return Array.isArray(value) ? (value[0] || '') : (value || '')
}

function copyRoute() {
  const page = Number(routeValue('page') || 1)
  Object.assign(query, {
    search: routeValue('search'),
    unread: routeValue('unread'),
    disposition: routeValue('disposition'),
    page: Number.isInteger(page) && page > 0 ? page : 1,
  })
}

function routeQuery() {
  return Object.fromEntries(Object.entries(query).filter(([, value]) => value !== '' && value !== 1))
}

async function sync(next) {
  Object.assign(query, next)
  const nextQuery = routeQuery()
  if (JSON.stringify(nextQuery) === JSON.stringify(route.query)) {
    await load()
    return
  }
  await router.replace({ query: nextQuery })
}

function applyFilters(next) {
  return sync({ ...next, page: 1 })
}

function reset() {
  return sync({ search: '', page: 1, unread: '', disposition: '' })
}

async function load() {
  request.begin()
  try {
    const res = await api.get('/alerts', { params: {
      search: query.search || undefined,
      page: query.page,
      size: 20,
      unread: query.unread || undefined,
      disposition: query.disposition || undefined,
    } })
    alerts.value = res.data.items || []
    total.value = res.data.total || 0
    request.succeed()
  } catch {
    request.fail('告警加载失败，当前保留上一次成功数据。')
  }
}

async function markRead(id) {
  marking.value = true
  try {
    await api.put(`/alerts/${id}/read`)
    await load()
    await alertStore.fetchUnreadCount()
  } finally {
    marking.value = false
  }
}

async function markAll() {
  marking.value = true
  try {
    await api.put('/alerts/read-all')
    await load()
    await alertStore.fetchUnreadCount()
  } finally {
    marking.value = false
  }
}

function openHolding(alert) {
  if (alert.holding_id) router.push(`/holdings/${alert.holding_id}`)
}

function dispositionLabel(disposition) {
  return { triggered: '待处理', closed: '已关闭', rearmed: '已重新布防' }[disposition] || '待处理'
}

onMounted(() => {
  copyRoute()
  void load()
})
watch(() => route.query, () => {
  copyRoute()
  void load()
}, { deep: true })
</script>

<template>
  <section aria-labelledby="alerts-title">
    <div class="page-heading">
      <div><h1 id="alerts-title" class="page-title">告警与持仓处置</h1><p class="page-subtitle">标记已读只更新阅读状态，不会关闭或修改持仓。</p></div>
      <el-button :loading="marking" @click="markAll">全部标记已读</el-button>
    </div>

    <section class="alert-filters" aria-label="告警筛选">
      <el-input
        v-model="query.search"
        aria-label="搜索告警"
        placeholder="搜索持仓名称或代码"
        maxlength="100"
        clearable
        @clear="applyFilters({ search: '' })"
        @keyup.enter="applyFilters({ search: query.search })"
      />
      <el-button :icon="Search" @click="applyFilters({ search: query.search })">搜索</el-button>
      <el-select v-model="query.unread" aria-label="阅读状态" @change="value => applyFilters({ unread: value })">
        <el-option label="全部阅读状态" value="" />
        <el-option label="未读" value="true" />
        <el-option label="已读" value="false" />
      </el-select>
      <el-select v-model="query.disposition" aria-label="处置状态" @change="value => applyFilters({ disposition: value })">
        <el-option label="全部处置状态" value="" />
        <el-option label="待处理" value="triggered" />
        <el-option label="已关闭" value="closed" />
        <el-option label="已重新布防" value="rearmed" />
      </el-select>
      <el-button v-if="hasFilters" @click="reset">重置筛选</el-button>
      <span class="filter-total">共 {{ total }} 条</span>
    </section>

    <section class="panel alerts-panel">
      <DataState v-if="request.initialLoading.value" kind="loading" title="正在加载告警" />
      <DataState v-else-if="request.error.value && !request.hasData.value" kind="error" title="暂时无法加载告警" :description="request.error.value" action-label="重试" @action="load" />
      <DataState
        v-else-if="!alerts.length"
        :title="hasFilters ? '没有匹配的告警' : '还没有告警'"
        :description="hasFilters ? '当前筛选条件下没有结果，历史告警仍会保留。' : '触发止损后，告警快照会显示在这里。'"
        :action-label="hasFilters ? '重置筛选' : undefined"
        @action="reset"
      />
      <div v-else class="alert-list">
        <article v-for="alert in alerts" :key="alert.id" class="alert-card" :class="{ unread: !alert.read }">
          <header><div><strong>{{ alert.holding_name }}</strong><small>{{ alert.holding_code }} · {{ dispositionLabel(alert.disposition) }}</small></div><el-tag :type="alert.read ? 'info' : 'warning'">{{ alert.read ? '已读' : '未读' }}</el-tag></header>
          <div class="snapshot"><span>当前价 <strong class="number">{{ formatMoney(alert.current_price) }}</strong></span><span>止损价 <strong class="number">{{ formatMoney(alert.trigger_price) }}</strong></span></div>
          <footer><time>{{ formatTime(alert.created_at) }}</time><span><el-button v-if="alert.holding_id" link @click="openHolding(alert)">查看持仓</el-button><el-button v-if="!alert.read" link type="primary" :loading="marking" @click="markRead(alert.id)">标记已读</el-button></span></footer>
        </article>
      </div>
      <el-pagination v-if="total > 20" :current-page="query.page" :page-size="20" :total="total" layout="prev, pager, next" @current-change="page => sync({ page })" />
    </section>
  </section>
</template>

<style scoped>
.alert-filters { margin-bottom: 12px; display: grid; grid-template-columns: minmax(220px, 1fr) auto 170px 170px auto auto; align-items: center; gap: 10px; }
.filter-total { justify-self: end; color: var(--color-text-muted); font-size: 12px; white-space: nowrap; }
.alerts-panel { overflow: hidden; }
.alert-list { display: grid; }
.alert-card { display: grid; gap: 12px; padding: 15px 18px; border-bottom: 1px solid var(--color-border); }
.alert-card.unread { background: var(--color-warning-soft); }
.alert-card header, .alert-card footer, .snapshot { display: flex; justify-content: space-between; gap: 15px; }
.alert-card header > div { display: grid; gap: 3px; }
.alert-card small, .alert-card time { color: var(--color-text-muted); font-size: 12px; }
.snapshot { justify-content: flex-start; }
.snapshot span { display: grid; gap: 3px; }
.alert-card footer > span { display: flex; gap: 6px; }
.el-pagination { justify-content: center; padding: 14px; }
@media (max-width: 1023px) { .alert-filters { grid-template-columns: minmax(0, 1fr) auto 1fr 1fr; } .filter-total { grid-column: -2 / -1; } }
@media (max-width: 767px) { .alert-filters { grid-template-columns: minmax(0, 1fr) auto; } .alert-filters :deep(.el-select) { width: 100%; } .filter-total { grid-column: auto; } .alert-card header, .alert-card footer { align-items: flex-start; flex-direction: column; } .snapshot { display: grid; grid-template-columns: 1fr 1fr; } }
</style>
