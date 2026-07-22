<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import DataState from '../components/DataState.vue'
import { useAlertStore } from '../stores/alert'
import { formatMoney, formatTime } from '../utils/format'
import { useRequestState } from '../utils/requestState'

const alerts = ref([])
const markingAll = ref(false)
const markingIds = ref(new Set())
const request = useRequestState()
const alertStore = useAlertStore()
const unreadCount = computed(() => alerts.value.filter(item => !item.read).length)

async function load() {
  request.begin()
  try {
    const res = await api.get('/alerts')
    alerts.value = res.data.items || []
    request.succeed()
  } catch {
    request.fail('告警历史加载失败，请稍后重试。')
  }
}

async function markRead(id) {
  if (markingIds.value.has(id)) return
  markingIds.value = new Set([...markingIds.value, id])
  try {
    await api.put(`/alerts/${id}/read`)
    const target = alerts.value.find(item => item.id === id)
    if (target) target.read = true
    await alertStore.fetchUnreadCount()
  } finally {
    const next = new Set(markingIds.value)
    next.delete(id)
    markingIds.value = next
  }
}

async function markAllRead() {
  if (markingAll.value || unreadCount.value === 0) return
  markingAll.value = true
  try {
    await api.put('/alerts/read-all')
    alerts.value = alerts.value.map(item => ({ ...item, read: true }))
    await alertStore.fetchUnreadCount()
  } finally {
    markingAll.value = false
  }
}

onMounted(load)
</script>

<template>
  <section aria-labelledby="alerts-title">
    <div class="page-heading">
      <div><h1 id="alerts-title" class="page-title">告警历史</h1><p class="page-subtitle">保留触发时的价格快照，帮助复盘风险</p></div>
      <el-button v-if="alerts.length" :disabled="unreadCount === 0" :loading="markingAll" @click="markAllRead">全部标记已读</el-button>
    </div>

    <div v-if="request.error.value && request.hasData.value" class="status-strip is-warning"><span>{{ request.error.value }}</span><el-button link @click="load">重试</el-button></div>

    <section class="panel alerts-panel" aria-label="告警记录">
      <DataState v-if="request.initialLoading.value" kind="loading" title="正在加载告警" />
      <DataState v-else-if="request.error.value && !request.hasData.value" kind="error" title="暂时无法加载告警" :description="request.error.value" action-label="重新加载" @action="load" />
      <DataState v-else-if="!alerts.length" title="暂无告警" description="当前没有止损触发记录，监控仍会继续运行。" />

      <div v-else class="desktop-only alerts-table">
        <el-table :data="alerts" :row-class-name="({ row }) => row.read ? '' : 'unread-row'">
          <el-table-column label="持仓" min-width="190"><template #default="{ row }"><div class="identity"><strong>{{ row.holding_name }}</strong><span>{{ row.holding_code }}</span></div></template></el-table-column>
          <el-table-column label="触发快照" min-width="210"><template #default="{ row }"><div class="snapshot number"><span>当前 <strong>{{ formatMoney(row.current_price) }}</strong></span><span>止损 <strong>{{ formatMoney(row.trigger_price) }}</strong></span></div></template></el-table-column>
          <el-table-column label="触发时间" min-width="190"><template #default="{ row }"><span class="number">{{ formatTime(row.created_at) }}</span></template></el-table-column>
          <el-table-column label="状态" width="105"><template #default="{ row }"><el-tag :type="row.read ? 'info' : 'warning'">{{ row.read ? '✓ 已读' : '● 未读' }}</el-tag></template></el-table-column>
          <el-table-column label="操作" width="110"><template #default="{ row }"><el-button v-if="!row.read" type="primary" link :loading="markingIds.has(row.id)" @click="markRead(row.id)">标记已读</el-button><span v-else class="read-placeholder">已处理</span></template></el-table-column>
        </el-table>
      </div>

      <div v-if="alerts.length" class="mobile-only alert-list">
        <article v-for="alert in alerts" :key="alert.id" class="alert-card" :class="{ 'alert-card--unread': !alert.read }">
          <header><div><strong>{{ alert.holding_name }}</strong><small>{{ alert.holding_code }}</small></div><el-tag :type="alert.read ? 'info' : 'warning'" size="small">{{ alert.read ? '✓ 已读' : '● 未读' }}</el-tag></header>
          <div class="alert-card__prices"><span><small>触发时当前价</small><strong class="number">{{ formatMoney(alert.current_price) }}</strong></span><span><small>止损价</small><strong class="number">{{ formatMoney(alert.trigger_price) }}</strong></span></div>
          <footer><time>{{ formatTime(alert.created_at) }}</time><el-button v-if="!alert.read" type="primary" link :loading="markingIds.has(alert.id)" @click="markRead(alert.id)">标记已读</el-button></footer>
        </article>
      </div>
    </section>
  </section>
</template>

<style scoped>
.alerts-panel { overflow: hidden; }
.alerts-table { padding: 8px 18px 16px; }
.identity { display: grid; gap: 4px; }
.identity span, .snapshot, .read-placeholder { color: var(--color-text-muted); font-size: 12px; }
.snapshot { display: flex; gap: 18px; }
:deep(.unread-row) { --el-table-tr-bg-color: var(--color-warning-soft); }
.alert-list { padding: 12px; }
.alert-card { padding: 15px; display: grid; gap: 14px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; }
.alert-card + .alert-card { margin-top: 10px; }
.alert-card--unread { background: var(--color-warning-soft); border-color: #ecd7b5; }
.alert-card header, .alert-card footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.alert-card header > div { display: grid; gap: 3px; }
.alert-card small, .alert-card time { color: var(--color-text-muted); font-size: 11px; }
.alert-card__prices { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.alert-card__prices > span { display: grid; gap: 4px; }
.alert-card footer { padding-top: 10px; border-top: 1px solid rgba(120,120,110,.15); }
</style>
