<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import DataState from '../components/DataState.vue'
import FilterToolbar from '../components/FilterToolbar.vue'
import { useAlertStore } from '../stores/alert'
import { formatMoney, formatTime } from '../utils/format'
import { useRequestState } from '../utils/requestState'

const route = useRoute(); const router = useRouter(); const alerts = ref([]); const total = ref(0); const marking = ref(false); const request = useRequestState(); const alertStore = useAlertStore()
const query = reactive({ search: '', lifecycle: '', risk: '', sort: 'newest', page: 1, unread: '', disposition: '' })
function copyRoute() { Object.assign(query, { ...query, ...route.query, page: Number(route.query.page || 1) }) }
function sync(next) { Object.assign(query, next); router.replace({ query: Object.fromEntries(Object.entries(query).filter(([, value]) => value !== '' && value !== 1)) }); load() }
function reset() { sync({ search: '', lifecycle: '', risk: '', sort: 'newest', page: 1, unread: '', disposition: '' }) }
async function load() { request.begin(); try { const res = await api.get('/alerts', { params: { page: query.page, size: 20, unread: query.unread || undefined, disposition: query.disposition || undefined } }); alerts.value = res.data.items || []; total.value = res.data.total || 0; request.succeed() } catch { request.fail('Unable to load alerts; the previous data remains visible.') } }
const visible = computed(() => { const needle = query.search.toLowerCase(); return alerts.value.filter(item => !needle || `${item.holding_name} ${item.holding_code}`.toLowerCase().includes(needle)) })
async function markRead(id) { marking.value = true; try { await api.put(`/alerts/${id}/read`); await load(); await alertStore.fetchUnreadCount() } finally { marking.value = false } }
async function markAll() { marking.value = true; try { await api.put('/alerts/read-all'); await load(); await alertStore.fetchUnreadCount() } finally { marking.value = false } }
function openPosition(alert) { if (alert.position_id) router.push(`/positions/${alert.position_id}`) }
onMounted(() => { copyRoute(); load() }); watch(() => route.query, copyRoute)
</script>

<template>
  <section aria-labelledby="alerts-title">
    <div class="page-heading"><div><h1 id="alerts-title" class="page-title">Alerts and disposition</h1><p class="page-subtitle">Reading an alert never acknowledges, rearms, or closes its position.</p></div><el-button :loading="marking" @click="markAll">Mark all read</el-button></div>
    <FilterToolbar :query="query" :total="total" @update:query="sync" @reset="reset" />
    <div class="alert-selects"><el-select v-model="query.unread" aria-label="Read status" @change="sync(query)"><el-option label="All reading states" value="" /><el-option label="Unread" value="true" /></el-select><el-select v-model="query.disposition" aria-label="Disposition" @change="sync(query)"><el-option label="All dispositions" value="" /><el-option label="Triggered" value="triggered" /><el-option label="Rearmed" value="rearmed" /><el-option label="Closed" value="closed" /></el-select></div>
    <section class="panel alerts-panel"><DataState v-if="request.initialLoading.value" kind="loading" title="Loading alerts" /><DataState v-else-if="request.error.value && !request.hasData.value" kind="error" title="Unable to load alerts" :description="request.error.value" action-label="Retry" @action="load" /><DataState v-else-if="!visible.length" title="No matching alerts" description="This may be an empty filter result; alert history can still exist." action-label="Reset filters" @action="reset" />
      <div v-else class="alert-list"><article v-for="alert in visible" :key="alert.id" class="alert-card" :class="{ unread: !alert.read }"><header><div><strong>{{ alert.holding_name }}</strong><small>{{ alert.holding_code }} · {{ alert.disposition || 'triggered' }}</small></div><el-tag :type="alert.read ? 'info' : 'warning'">{{ alert.read ? 'Read' : 'Unread' }}</el-tag></header><div class="snapshot"><span>Current <strong class="number">{{ formatMoney(alert.current_price) }}</strong></span><span>Stop <strong class="number">{{ formatMoney(alert.trigger_price) }}</strong></span></div><footer><time>{{ formatTime(alert.created_at) }}</time><span><el-button v-if="alert.position_id" link @click="openPosition(alert)">Position</el-button><el-button v-if="!alert.read" link type="primary" :loading="marking" @click="markRead(alert.id)">Mark read</el-button></span></footer></article></div>
      <el-pagination v-if="total > 20" :current-page="query.page" :page-size="20" :total="total" layout="prev, pager, next" @current-change="page => sync({ ...query, page })" />
    </section>
  </section>
</template>

<style scoped>
.alert-selects { display: flex; justify-content: flex-end; gap: 10px; margin: 10px 0; }.alerts-panel { overflow: hidden; }.alert-list { display: grid; }.alert-card { display: grid; gap: 12px; padding: 15px 18px; border-bottom: 1px solid var(--color-border); }.alert-card.unread { background: var(--color-warning-soft); }.alert-card header, .alert-card footer, .snapshot { display: flex; justify-content: space-between; gap: 15px; }.alert-card header > div { display: grid; gap: 3px; }.alert-card small, .alert-card time { color: var(--color-text-muted); font-size: 12px; }.snapshot { justify-content: flex-start; }.snapshot span { display: grid; gap: 3px; }.alert-card footer > span { display: flex; gap: 6px; }.el-pagination { justify-content: center; padding: 14px; } @media (max-width: 767px) { .alert-selects { display: grid; grid-template-columns: 1fr 1fr; }.alert-card header, .alert-card footer { align-items: flex-start; flex-direction: column; }.snapshot { display: grid; grid-template-columns: 1fr 1fr; } }
</style>
