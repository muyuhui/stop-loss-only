<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { requestPriceRefresh } from '../api'
import DataState from '../components/DataState.vue'
import { formatAssetMoney, formatSignedPercent, formatTime, stopLossRisk, valueTone } from '../utils/format'
import { priceInputMeta, stopLossInputMeta } from '../utils/holdingForm'
import { holdingStatusLabel, holdingStatusTag } from '../utils/holdingStatus'
import { summarizeRefresh } from '../utils/refreshResult'
import { useRequestState } from '../utils/requestState'

const route = useRoute()
const router = useRouter()
const holding = ref({})
const editMode = ref(false)
const saving = ref(false)
const closing = ref(false)
const deleting = ref(false)
const refreshing = ref(false)
const closePrice = ref(null)
const request = useRequestState()
const editForm = reactive({ name: '', stop_loss_method: '', stop_loss_value: null })

const priceMeta = computed(() => priceInputMeta(holding.value.type))
const editMeta = computed(() => stopLossInputMeta(editForm.stop_loss_method, holding.value.type))
const holdingRisk = computed(() => stopLossRisk(holding.value.stop_loss_distance_pct, holding.value.status))

async function load() {
  request.begin()
  try {
    const res = await api.get(`/holdings/${route.params.id}`)
    holding.value = res.data
    editForm.name = res.data.name
    editForm.stop_loss_method = res.data.stop_loss_method
    editForm.stop_loss_value = res.data.stop_loss_value
    request.succeed()
  } catch {
    request.fail('持仓详情加载失败，请返回列表或重试。')
  }
}

async function saveEdit() {
  if (saving.value) return
  saving.value = true
  try {
    await api.put(`/holdings/${route.params.id}`, {
      name: editForm.name.trim(),
      stop_loss_method: editForm.stop_loss_method,
      stop_loss_value: Number(editForm.stop_loss_value),
    })
    ElMessage.success('持仓与止损参数已更新')
    editMode.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function refreshPrice() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    const res = await requestPriceRefresh()
    const summary = summarizeRefresh(res.data)
    ElMessage[summary.type](summary.message)
    await load()
  } finally {
    refreshing.value = false
  }
}

async function closeHolding() {
  if (closing.value || !closePrice.value) return
  try {
    await ElMessageBox.confirm(`将以 ${formatAssetMoney(closePrice.value, holding.value.type)} 手动平仓，确认继续？`, '确认平仓', {
      confirmButtonText: '确认平仓', cancelButtonText: '取消', type: 'warning',
    })
  } catch { return }
  closing.value = true
  try {
    await api.post(`/holdings/${route.params.id}/close`, { close_price: Number(closePrice.value) })
    ElMessage.success('持仓已关闭')
    closePrice.value = null
    await load()
  } finally {
    closing.value = false
  }
}

async function deleteHolding() {
  if (deleting.value) return
  try {
    await ElMessageBox.confirm('删除后无法恢复，但已经产生的历史告警仍会保留。', '确认删除持仓', {
      confirmButtonText: '永久删除', cancelButtonText: '取消', type: 'error',
    })
  } catch { return }
  deleting.value = true
  try {
    await api.delete(`/holdings/${route.params.id}`)
    ElMessage.success('持仓已删除')
    await router.push('/holdings')
  } finally {
    deleting.value = false
  }
}

function methodLabel(method) {
  return { fixed: '固定价格', percentage: '百分比', trailing: '移动（追踪）' }[method] || method
}

onMounted(load)
</script>

<template>
  <section aria-labelledby="holding-title">
    <DataState v-if="request.initialLoading.value" kind="loading" title="正在加载持仓详情" />
    <DataState v-else-if="request.error.value && !request.hasData.value" kind="error" title="暂时无法加载持仓" :description="request.error.value" action-label="重新加载" @action="load" />

    <div v-else-if="holding.id" class="detail-stack">
      <div class="detail-heading">
        <button type="button" class="back-button" aria-label="返回持仓管理" @click="router.push('/holdings')">←</button>
        <div>
          <h1 id="holding-title" class="page-title">{{ holding.name }}</h1>
          <p class="page-subtitle">{{ holding.code }} · {{ holding.type === 'stock' ? '股票' : '基金' }} · 更新于 {{ formatTime(holding.updated_at) }}</p>
        </div>
        <el-tag class="detail-heading__status" :type="holdingStatusTag(holding.status)">{{ holdingStatusLabel(holding.status) }}</el-tag>
      </div>

      <div v-if="request.error.value" class="status-strip is-warning"><span>{{ request.error.value }}</span><el-button link @click="load">重试</el-button></div>

      <section class="detail-summary" aria-label="持仓风险摘要">
        <article><span>当前价</span><strong class="number">{{ formatAssetMoney(holding.current_price, holding.type) }}</strong><small>买入 {{ formatAssetMoney(holding.buy_price, holding.type) }}</small></article>
        <article><span>未实现盈亏</span><strong class="number" :class="`tone-${valueTone(holding.profit_loss_pct)}`">{{ formatSignedPercent(holding.profit_loss_pct) }}</strong><small>{{ holding.quantity }} 份</small></article>
        <article><span>止损价</span><strong class="number">{{ formatAssetMoney(holding.stop_loss_price, holding.type) }}</strong><small>{{ methodLabel(holding.stop_loss_method) }}</small></article>
        <article :class="`summary-risk--${holdingRisk.level}`"><span>距止损</span><strong class="number">{{ formatSignedPercent(holding.stop_loss_distance_pct) }}</strong><small>{{ holdingRisk.label }}</small></article>
      </section>

      <section class="panel" aria-labelledby="stop-settings-title">
        <header class="panel__header">
          <div><h2 id="stop-settings-title" class="panel__title">止损设置</h2><span class="panel-hint">历史最高 {{ formatAssetMoney(holding.highest_price, holding.type) }}</span></div>
          <div class="panel-actions">
            <el-button :loading="refreshing" @click="refreshPrice">刷新价格</el-button>
            <el-button v-if="holding.status === 'holding' && !editMode" type="primary" @click="editMode = true">修改止损</el-button>
          </div>
        </header>

        <div v-if="!editMode" class="stop-settings-view">
          <div><span>止损方式</span><strong>{{ methodLabel(holding.stop_loss_method) }}</strong></div>
          <div><span>止损参数</span><strong class="number">{{ holding.stop_loss_value }}{{ holding.stop_loss_method === 'fixed' ? ' 元' : '%' }}</strong></div>
          <div><span>行情来源</span><strong>{{ holding.quote_source || '暂无' }}</strong></div>
          <div><span>行情时间</span><strong class="number">{{ formatTime(holding.quoted_at) }}</strong></div>
        </div>

        <el-form v-else :model="editForm" label-position="top" class="edit-form" @submit.prevent="saveEdit">
          <el-form-item label="持仓名称"><el-input v-model="editForm.name" /></el-form-item>
          <el-form-item label="止损方式"><el-select v-model="editForm.stop_loss_method"><el-option label="百分比止损" value="percentage" /><el-option label="固定价格止损" value="fixed" /><el-option label="移动止损" value="trailing" /></el-select></el-form-item>
          <el-form-item :label="`止损参数（${editMeta.unit}）`"><el-input-number v-model="editForm.stop_loss_value" :precision="editMeta.precision" :step="editMeta.step" :min="editMeta.min" :controls="false" /></el-form-item>
          <p class="edit-help">{{ editMeta.help }}</p>
          <div class="edit-actions"><el-button @click="editMode = false">取消</el-button><el-button type="primary" native-type="submit" :loading="saving">保存修改</el-button></div>
        </el-form>
      </section>

      <section v-if="holding.status !== 'closed'" class="panel" aria-labelledby="close-title">
        <header class="panel__header"><div><h2 id="close-title" class="panel__title">手动平仓</h2><span class="panel-hint">记录实际平仓价格并结束持仓监控</span></div></header>
        <div class="close-form">
          <el-input-number v-model="closePrice" :precision="priceMeta.precision" :step="priceMeta.step" :min="priceMeta.min" :controls="false" placeholder="输入平仓价" aria-label="平仓价格" />
          <el-button type="warning" :disabled="!closePrice" :loading="closing" @click="closeHolding">确认平仓</el-button>
        </div>
      </section>

      <section class="danger-zone" aria-labelledby="danger-title">
        <div><h2 id="danger-title">危险操作</h2><p>删除持仓不可撤销。历史告警快照不会被删除。</p></div>
        <el-button type="danger" plain :loading="deleting" @click="deleteHolding">删除持仓</el-button>
      </section>
    </div>
  </section>
</template>

<style scoped>
.detail-stack { display: grid; gap: 16px; }
.detail-heading { min-height: 50px; display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 13px; }
.back-button { width: 38px; height: 38px; color: var(--color-brand); background: var(--color-brand-soft); border: 0; border-radius: 50%; cursor: pointer; font-size: 20px; }
.detail-heading__status { justify-self: end; }
.detail-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.detail-summary article { min-width: 0; padding: 18px; display: grid; gap: 6px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; box-shadow: var(--shadow-panel); }
.detail-summary span, .stop-settings-view span { color: var(--color-text-soft); font-size: 12px; }
.detail-summary strong { font-size: 22px; }
.detail-summary small, .panel-hint { color: var(--color-text-muted); font-size: 11px; }
.summary-risk--danger { background: var(--color-danger-soft) !important; border-color: #edcbc8 !important; }
.summary-risk--warning { background: var(--color-warning-soft) !important; border-color: #ecd7b5 !important; }
.summary-risk--safe strong { color: var(--color-success); }
.panel__header > div:first-child { display: grid; gap: 3px; }
.panel-actions { display: flex; gap: 8px; }
.stop-settings-view { padding: 20px; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 20px; }
.stop-settings-view > div { display: grid; gap: 6px; }
.stop-settings-view strong { font-size: 14px; }
.edit-form { padding: 20px; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0 16px; }
.edit-form :deep(.el-input-number), .edit-form :deep(.el-select) { width: 100%; }
.edit-help { grid-column: 1 / -1; margin: -6px 0 16px; color: var(--color-text-soft); font-size: 12px; }
.edit-actions { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: 8px; }
.close-form { padding: 20px; display: flex; align-items: center; gap: 10px; }
.close-form :deep(.el-input-number) { width: 200px; }
.danger-zone { padding: 18px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; background: #fffafa; border: 1px solid #efcfcc; border-radius: 12px; }
.danger-zone h2 { margin: 0; color: var(--color-danger); font-size: 15px; }
.danger-zone p { margin: 5px 0 0; color: var(--color-text-soft); font-size: 12px; }
@media (max-width: 1023px) { .detail-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } .stop-settings-view { grid-template-columns: repeat(2, minmax(0, 1fr)); } .edit-form { grid-template-columns: 1fr 1fr; } }
@media (max-width: 767px) {
  .detail-heading { align-items: start; }
  .detail-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .detail-summary article { padding: 14px; }
  .detail-summary strong { font-size: 18px; }
  .panel__header { align-items: flex-start; padding-top: 12px; padding-bottom: 12px; flex-direction: column; }
  .panel-actions { width: 100%; }
  .panel-actions .el-button { flex: 1; }
  .stop-settings-view, .edit-form { grid-template-columns: 1fr; padding: 16px; }
  .edit-help, .edit-actions { grid-column: 1; }
  .edit-actions .el-button { flex: 1; }
  .close-form { align-items: stretch; flex-direction: column; padding: 16px; }
  .close-form :deep(.el-input-number) { width: 100%; }
  .danger-zone { align-items: stretch; flex-direction: column; }
}
</style>
