<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import DataState from '../components/DataState.vue'
import HoldingForm from '../components/HoldingForm.vue'
import { formatAssetMoney, formatSignedPercent, stopLossRisk, valueTone } from '../utils/format'
import { holdingStatusLabel, holdingStatusTag } from '../utils/holdingStatus'
import { useRequestState } from '../utils/requestState'

const holdings = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const dialogVisible = ref(false)
const request = useRequestState()
const router = useRouter()

async function load() {
  request.begin()
  try {
    const res = await api.get('/holdings', { params: { page: page.value, size: size.value } })
    holdings.value = res.data.items || []
    total.value = res.data.total || 0
    request.succeed()
  } catch {
    request.fail('持仓列表加载失败，请检查服务后重试。')
  }
}

function onCreated() {
  dialogVisible.value = false
  page.value = 1
  load()
}

function methodLabel(method) {
  return { fixed: '固定价', percentage: '百分比', trailing: '追踪' }[method] || method
}

onMounted(load)
</script>

<template>
  <section aria-labelledby="holdings-title">
    <div class="page-heading">
      <div>
        <h1 id="holdings-title" class="page-title">持仓管理</h1>
        <p class="page-subtitle">查看价格与止损距离，快速进入单笔持仓</p>
      </div>
      <el-button type="primary" @click="dialogVisible = true">新增持仓</el-button>
    </div>

    <div v-if="request.error.value && request.hasData.value" class="status-strip is-warning">
      <span>{{ request.error.value }}</span>
      <el-button size="small" link @click="load">重试</el-button>
    </div>

    <section class="panel holdings-panel" aria-label="持仓列表">
      <DataState v-if="request.initialLoading.value" kind="loading" title="正在加载持仓" />
      <DataState v-else-if="request.error.value && !request.hasData.value" kind="error" title="暂时无法加载持仓" :description="request.error.value" action-label="重新加载" @action="load" />
      <DataState v-else-if="!holdings.length" title="还没有持仓" description="添加第一笔持仓后即可开始监控价格和止损风险。" action-label="新增持仓" @action="dialogVisible = true" />

      <div v-else class="desktop-only holdings-table">
        <el-table :data="holdings" @row-click="row => router.push(`/holdings/${row.id}`)">
          <el-table-column label="持仓" min-width="190">
            <template #default="{ row }"><div class="identity"><strong>{{ row.name }}</strong><span>{{ row.code }} · {{ row.type === 'stock' ? '股票' : '基金' }}</span></div></template>
          </el-table-column>
          <el-table-column label="持有" min-width="150">
            <template #default="{ row }"><div class="cell-stack number"><strong>{{ row.quantity }} 份</strong><span>成本 {{ formatAssetMoney(row.buy_price, row.type) }}</span></div></template>
          </el-table-column>
          <el-table-column label="当前表现" min-width="160">
            <template #default="{ row }"><div class="cell-stack number"><strong>{{ formatAssetMoney(row.current_price, row.type) }}</strong><span :class="`tone-${valueTone(row.profit_loss_pct)}`">{{ formatSignedPercent(row.profit_loss_pct) }}</span></div></template>
          </el-table-column>
          <el-table-column label="止损风险" min-width="195">
            <template #default="{ row }"><div class="cell-stack number"><strong>{{ formatAssetMoney(row.stop_loss_price, row.type) }} · {{ methodLabel(row.stop_loss_method) }}</strong><span :class="`risk-${stopLossRisk(row.stop_loss_distance_pct, row.status).level}`">{{ stopLossRisk(row.stop_loss_distance_pct, row.status).label }} {{ formatSignedPercent(row.stop_loss_distance_pct) }}</span></div></template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }"><el-tag :type="holdingStatusTag(row.status)">{{ holdingStatusLabel(row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" width="90">
            <template #default="{ row }"><el-button type="primary" link @click.stop="router.push(`/holdings/${row.id}`)">详情</el-button></template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="holdings.length" class="mobile-only mobile-list">
        <button v-for="row in holdings" :key="row.id" type="button" class="position-card" @click="router.push(`/holdings/${row.id}`)">
          <span class="position-card__header">
            <span><strong>{{ row.name }}</strong><small>{{ row.code }} · {{ methodLabel(row.stop_loss_method) }}</small></span>
            <el-tag :type="holdingStatusTag(row.status)" size="small">{{ holdingStatusLabel(row.status) }}</el-tag>
          </span>
          <span class="position-card__metrics">
            <span><small>当前价</small><strong class="number">{{ formatAssetMoney(row.current_price, row.type) }}</strong></span>
            <span><small>盈亏</small><strong class="number" :class="`tone-${valueTone(row.profit_loss_pct)}`">{{ formatSignedPercent(row.profit_loss_pct) }}</strong></span>
            <span><small>止损价</small><strong class="number">{{ formatAssetMoney(row.stop_loss_price, row.type) }}</strong></span>
            <span><small>距止损</small><strong class="number" :class="`risk-${stopLossRisk(row.stop_loss_distance_pct, row.status).level}`">{{ formatSignedPercent(row.stop_loss_distance_pct) }}</strong></span>
          </span>
          <span class="position-card__footer"><span :class="`risk-${stopLossRisk(row.stop_loss_distance_pct, row.status).level}`">{{ stopLossRisk(row.stop_loss_distance_pct, row.status).label }}</span><span>查看详情 →</span></span>
        </button>
      </div>
    </section>

    <el-pagination v-if="total > size" v-model:current-page="page" v-model:page-size="size" :total="total" layout="prev, pager, next, total" class="holdings-pagination" @current-change="load" />

    <el-dialog v-model="dialogVisible" title="新增持仓" width="560px" destroy-on-close>
      <HoldingForm @success="onCreated" @cancel="dialogVisible = false" />
    </el-dialog>
  </section>
</template>

<style scoped>
.holdings-panel { overflow: hidden; }
.holdings-table { padding: 8px 18px 16px; }
.identity, .cell-stack { display: grid; gap: 4px; }
.identity span, .cell-stack span { color: var(--color-text-muted); font-size: 12px; }
.cell-stack .tone-profit { color: var(--color-profit); }
.cell-stack .tone-loss { color: var(--color-loss); }
.risk-danger { color: var(--color-danger) !important; }
.risk-warning { color: var(--color-warning) !important; }
.risk-safe { color: var(--color-success) !important; }
.holdings-pagination { margin-top: 16px; justify-content: flex-end; }
.mobile-list { padding: 12px; }
.position-card { width: 100%; padding: 15px; display: grid; gap: 14px; color: var(--color-text); text-align: left; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; }
.position-card + .position-card { margin-top: 10px; }
.position-card__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.position-card__header > span { display: grid; gap: 4px; }
.position-card__header small, .position-card__metrics small { color: var(--color-text-muted); font-size: 11px; }
.position-card__metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 13px; }
.position-card__metrics > span { display: grid; gap: 4px; }
.position-card__footer { padding-top: 11px; display: flex; align-items: center; justify-content: space-between; gap: 8px; color: var(--color-text-soft); border-top: 1px solid var(--color-border); font-size: 12px; font-weight: 650; }
@media (max-width: 900px) { .holdings-table { display: none !important; } .mobile-list { display: block; } }
@media (max-width: 767px) { .holdings-pagination { justify-content: center; } }
</style>
