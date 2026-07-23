<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DataState from '../components/DataState.vue'
import FilterToolbar from '../components/FilterToolbar.vue'
import StatusBanner from '../components/StatusBanner.vue'
import { usePositionsStore } from '../stores/positions'
import { formatDecimal, formatMoney } from '../utils/format'
import api from '../api'

const route = useRoute(); const router = useRouter(); const store = usePositionsStore()
const query = reactive({ search: '', lifecycle: '', risk: '', sort: 'risk', page: 1 })
const createOpen = ref(false); const creating = ref(false); const createError = ref('')
const createForm = reactive({ code: '', name: '', asset_type: 'stock', quantity: '', unit_cost: '', fees: '0', taxes: '0' })
function readQuery() { Object.assign(query, { search: route.query.search || '', lifecycle: route.query.lifecycle || '', risk: route.query.risk || '', sort: route.query.sort || 'risk', page: Number(route.query.page || 1) }) }
function syncQuery(next = query) { Object.assign(query, next); router.replace({ query: Object.fromEntries(Object.entries(query).filter(([, value]) => value !== '' && value !== 1)) }) }
const filtered = computed(() => {
  const needle = query.search.trim().toLowerCase()
  const rows = (store.data?.items || []).filter(row => (!needle || `${row.name} ${row.code}`.toLowerCase().includes(needle)) && (!query.lifecycle || row.lifecycle_status === query.lifecycle) && (!query.risk || row.risk_status === query.risk))
  return rows.sort((a, b) => query.sort === 'name' ? a.name.localeCompare(b.name) : query.sort === 'newest' ? b.id - a.id : Number(b.risk_status === 'triggered') - Number(a.risk_status === 'triggered') || b.id - a.id)
})
function reset() { syncQuery({ search: '', lifecycle: '', risk: '', sort: 'risk', page: 1 }) }
function detail(row) { router.push({ path: `/positions/${row.id}`, query: route.query }) }
async function createPosition() {
  createError.value = ''
  if (!createForm.code || !createForm.name || !createForm.quantity || !createForm.unit_cost) {
    createError.value = '请填写代码、名称、数量和单位成本。'
    return
  }
  creating.value = true
  try {
    const { data } = await api.post('/positions', createForm)
    createOpen.value = false
    await store.refresh()
    detail(data)
  } catch (error) {
    createError.value = error.response?.data?.detail?.error_code === 'new_authority_required'
      ? '当前仍处于兼容模式，暂不能创建新仓位。'
      : '新建仓位失败，请检查输入后重试。'
  } finally { creating.value = false }
}
onMounted(() => { readQuery(); store.refresh().catch(() => {}) })
watch(() => route.query, readQuery)
</script>

<template>
  <section aria-labelledby="positions-title">
    <div class="page-heading"><div><h1 id="positions-title" class="page-title">持仓与风险</h1><p class="page-subtitle">筛选、排序和页面上下文会保留在地址栏中。</p></div><div class="heading-actions"><el-button type="primary" @click="createOpen = true">新建仓位</el-button><el-button :loading="store.loading" @click="store.refresh().catch(() => {})">刷新</el-button></div></div>
    <FilterToolbar :query="query" :total="filtered.length" @update:query="syncQuery" @reset="reset" />
    <StatusBanner v-if="store.error && store.data" kind="warning" title="刷新失败，正在显示上一次成功数据" detail="可手动重试，数据不会被清空。" />
    <section class="panel positions-panel" aria-label="持仓列表">
      <DataState v-if="store.loading && !store.data" kind="loading" title="正在加载持仓" />
      <DataState v-else-if="store.error && !store.data" kind="error" title="无法加载持仓" description="请检查本地服务后重试。" action-label="重试" @action="store.refresh().catch(() => {})" />
      <DataState v-else-if="!filtered.length" title="没有匹配的持仓" description="可调整筛选条件，或稍后再试。" action-label="重置筛选" @action="reset" />
      <div v-else class="position-list">
        <button v-for="row in filtered" :key="row.id" type="button" class="position-row" @click="detail(row)">
          <span><strong>{{ row.name }}</strong><small>{{ row.code }} · {{ row.asset_type }}</small></span>
          <span><small>剩余数量</small><strong class="number">{{ formatDecimal(row.remaining_quantity, row.asset_type === 'fund' ? 6 : 0) }}</strong></span>
          <span><small>当前行情</small><strong class="number">{{ formatMoney(row.current_price) }}</strong><em>{{ row.quote_state }}</em></span>
          <span><small>风险状态</small><strong :class="`risk-${row.risk_status}`">{{ row.risk_status }}</strong><em>{{ row.lifecycle_status }}</em></span>
        </button>
      </div>
    </section>
    <el-dialog v-model="createOpen" title="新建仓位" width="min(560px, 94vw)" :close-on-click-modal="false">
      <form class="create-form" @submit.prevent="createPosition">
        <el-input v-model="createForm.code" aria-label="证券代码" placeholder="证券代码" />
        <el-input v-model="createForm.name" aria-label="证券名称" placeholder="证券名称" />
        <el-select v-model="createForm.asset_type" aria-label="资产类型"><el-option label="股票" value="stock" /><el-option label="基金" value="fund" /></el-select>
        <el-input v-model="createForm.quantity" aria-label="初始数量" placeholder="初始数量" /><el-input v-model="createForm.unit_cost" aria-label="单位成本" placeholder="单位成本" />
        <StatusBanner v-if="createError" kind="warning" title="无法创建仓位" :detail="createError" />
        <div class="dialog-actions"><el-button @click="createOpen = false">取消</el-button><el-button native-type="submit" type="primary" :loading="creating">创建并查看</el-button></div>
      </form>
    </el-dialog>
  </section>
</template>

<style scoped>
.positions-panel { margin-top: 14px; overflow: hidden; }.position-list { display: grid; }.position-row { display: grid; grid-template-columns: 2fr 1fr 1.2fr 1fr; align-items: center; gap: 16px; padding: 15px 18px; color: var(--color-text); text-align: left; background: var(--color-surface); border: 0; border-bottom: 1px solid var(--color-border); }.position-row:hover { background: var(--color-bg-soft); }.position-row > span { display: grid; gap: 3px; }.position-row small, em { color: var(--color-text-muted); font-size: 12px; font-style: normal; }.risk-triggered { color: var(--color-danger); }.risk-acknowledged { color: var(--color-warning); }.risk-normal { color: var(--color-success); }
.heading-actions, .dialog-actions { display: flex; gap: 8px; align-items: center; }.create-form { display: grid; gap: 12px; }.dialog-actions { justify-content: flex-end; margin-top: 4px; }
@media (max-width: 767px) { .position-row { grid-template-columns: 1fr 1fr; gap: 12px; }.position-row > :first-child { grid-column: 1 / -1; } }
</style>
