<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { refreshErrorMessage, requestHoldingHistory, requestPriceRefresh } from '../api'
import DataState from '../components/DataState.vue'
import HoldingPriceChart from '../components/HoldingPriceChart.vue'
import { formatAssetMoney, formatSignedPercent, formatTime, stopLossRisk, valueTone } from '../utils/format'
import { formatQuoteFreshness } from '../utils/market'
import { priceInputMeta, stopLossInputMeta } from '../utils/holdingForm'
import { holdingStatusLabel, holdingStatusTag } from '../utils/holdingStatus'
import { summarizeRefresh } from '../utils/refreshResult'
import { useRequestState } from '../utils/requestState'
import { quoteTrust } from '../utils/quoteTrust'
import { useRuntimeCapabilitiesStore } from '../stores/runtimeCapabilities'
import { useSettingsStore } from '../stores/settings'

const route = useRoute()
const router = useRouter()
const runtimeCapabilities = useRuntimeCapabilitiesStore()
const settingsStore = useSettingsStore()
const holding = ref({})
const editMode = ref(false)
const saving = ref(false)
const closing = ref(false)
const deleting = ref(false)
const refreshing = ref(false)
const closePrice = ref(null)
const request = useRequestState()
const historyData = ref(null)
const historyRange = ref('3m')
const historyLoading = ref(false)
const historyError = ref('')
let historyRequestId = 0
const aiReview = ref(null)
const aiReviewError = ref('')
const aiReviewPhase = ref('')
const stopHistory = ref([])
const stopHistoryError = ref('')
const editForm = reactive({ name: '', stop_loss_method: '', stop_loss_value: null })

const priceMeta = computed(() => priceInputMeta(holding.value.type))
const editMeta = computed(() => stopLossInputMeta(editForm.stop_loss_method, holding.value.type))
const holdingRisk = computed(() => stopLossRisk(holding.value.stop_loss_distance_pct, holding.value.status))
const trust = computed(() => quoteTrust(holding.value))
const addOnPlanningAvailable = computed(() => (
  holding.value.status === 'holding'
  && runtimeCapabilities.isAvailable('risk_plan_previews')
))
const aiReviewAvailable = computed(() => (
  holding.value.status && holding.value.status !== 'closed'
  && runtimeCapabilities.isAvailable('ai_holding_reviews')
))
const aiReviewLoading = computed(() => Boolean(aiReviewPhase.value))
const aiActionLabel = computed(() => ({
  execute_existing_stop: '执行既定止损',
  pause_add_on: '暂停加仓',
  continue_observing: '继续观察',
  review_risk_exposure: '重新评估风险暴露',
  open_add_on_preview: '可进一步试算加仓风险',
  refresh_data: '先补齐或刷新数据',
}[aiReview.value?.action] || '复盘完成'))
const aiConfidenceLabel = computed(() => ({ high: '高', medium: '中', low: '低' }[aiReview.value?.confidence] || '--'))

function openAddOnPlan() {
  router.push({ path: '/planner', query: { mode: 'add-on', holding_id: String(holding.value.id) } })
}

async function load() {
  request.begin()
  try {
    const res = await api.get(`/holdings/${route.params.id}`)
    holding.value = res.data
    editForm.name = res.data.name
    editForm.stop_loss_method = res.data.stop_loss_method
    editForm.stop_loss_value = res.data.stop_loss_value
    request.succeed()
    void loadHistory()
  } catch {
    request.fail('持仓详情加载失败，请返回列表或重试。')
  }
}

function aiErrorMessage(error) {
  const code = error?.response?.data?.detail?.error_code
  return {
    ai_not_configured: '请先在设置中配置 DeepSeek API Key。',
    ai_review_busy: '该持仓正在生成复盘，请稍后再试。',
    market_data_not_ready: '当前行情不可用于复盘，请重新刷新。',
    history_data_unavailable: '近期历史行情暂时不可用。',
    ai_timeout: 'DeepSeek 响应超时，请稍后重试。',
    ai_rate_limited: 'DeepSeek 请求过于频繁，请稍后重试。',
    ai_response_invalid: 'DeepSeek 返回了无法验证的结果，请重试。',
  }[code] || 'AI 复盘暂时不可用，请稍后重试。'
}

async function runAIReview() {
  if (aiReviewLoading.value || !holding.value.id) return
  aiReview.value = null
  aiReviewError.value = ''
  try {
    aiReviewPhase.value = 'refresh'
    await requestPriceRefresh({ holding_id: String(holding.value.id) })
    aiReviewPhase.value = 'history'
    await load()
    aiReviewPhase.value = 'analysis'
    const response = await api.post(`/ai/holdings/${holding.value.id}/review`, undefined, {
      timeout: 75000,
      suppressErrorCodes: ['ai_not_configured', 'ai_review_busy', 'market_data_not_ready', 'history_data_unavailable', 'ai_timeout', 'ai_rate_limited', 'ai_unavailable', 'ai_response_invalid'],
    })
    aiReview.value = response.data
  } catch (error) {
    aiReviewError.value = error?.response?.data?.detail?.error_code?.startsWith('refresh_')
      ? refreshErrorMessage(error)
      : aiErrorMessage(error)
  } finally {
    aiReviewPhase.value = ''
  }
}

async function loadStopHistory() {
  if (!holding.value.id) return
  stopHistoryError.value = ''
  try {
    const res = await api.get(`/holdings/${route.params.id}/stop-history`)
    stopHistory.value = res.data.items || []
  } catch {
    stopHistoryError.value = '无法加载止损调整记录。'
  }
}

async function loadHistory(range = historyRange.value) {
  const requestId = ++historyRequestId
  historyRange.value = range
  historyLoading.value = true
  historyError.value = ''
  try {
    const res = await requestHoldingHistory(route.params.id, range)
    if (requestId !== historyRequestId) return
    historyData.value = res.data
  } catch {
    if (requestId !== historyRequestId) return
    historyError.value = '历史行情加载失败，请稍后重试。'
  } finally {
    if (requestId === historyRequestId) historyLoading.value = false
  }
}

async function saveEdit() {
  if (saving.value) return
  saving.value = true
  try {
    if (holding.value.status === 'triggered') {
      await api.post(`/holdings/${route.params.id}/rearm`, {
        stop_loss_method: editForm.stop_loss_method,
        stop_loss_value: Number(editForm.stop_loss_value),
      })
      ElMessage.success('已重新布防，恢复监控')
    } else {
      await api.put(`/holdings/${route.params.id}`, {
        name: editForm.name.trim(),
        stop_loss_method: editForm.stop_loss_method,
        stop_loss_value: Number(editForm.stop_loss_value),
      })
      ElMessage.success('持仓与止损参数已更新')
    }
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
    const res = await requestPriceRefresh({ holding_id: route.params.id })
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

onMounted(async () => {
  await Promise.all([load(), settingsStore.fetchSettings()])
  void loadStopHistory()
})
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
        <article><span>当前价</span><strong class="number">{{ formatAssetMoney(holding.current_price, holding.type) }}</strong><small :class="`quote-tone--${trust.tone}`">{{ trust.text }} · {{ formatQuoteFreshness(holding.quoted_at) || '未定价' }}</small></article>
        <article><span>未实现盈亏</span><strong class="number" :class="`tone-${valueTone(holding.profit_loss_pct)}`">{{ formatSignedPercent(holding.profit_loss_pct) }}</strong><small>{{ holding.quantity }} 份</small></article>
        <article><span>止损价</span><strong class="number">{{ formatAssetMoney(holding.stop_loss_price, holding.type) }}</strong><small>{{ methodLabel(holding.stop_loss_method) }}</small></article>
        <article :class="`summary-risk--${holdingRisk.level}`"><span>距止损</span><strong class="number">{{ formatSignedPercent(holding.stop_loss_distance_pct) }}</strong><small>{{ holdingRisk.label }}</small></article>
      </section>

      <HoldingPriceChart
        :data="historyData"
        :asset-type="holding.type"
        :range="historyRange"
        :loading="historyLoading"
        :error="historyError"
        @range-change="loadHistory"
        @retry="loadHistory()"
      />

      <section v-if="aiReviewAvailable" class="panel ai-review-panel" aria-labelledby="ai-review-title">
        <header class="panel__header">
          <div><h2 id="ai-review-title" class="panel__title">AI 持仓复盘</h2><span class="panel-hint">基于近期行情、止损与风险预算，只做风险解释</span></div>
          <el-tag type="info">DeepSeek</el-tag>
        </header>
        <div class="ai-review-body">
          <template v-if="!settingsStore.deepseekApiKeyConfigured">
            <div class="ai-empty"><p>配置 DeepSeek 后可复盘近期行情与持仓风险。</p><el-button type="primary" plain @click="router.push('/settings')">前往设置</el-button></div>
          </template>
          <template v-else>
            <ol v-if="aiReviewLoading" class="ai-progress" aria-label="AI 复盘进度">
              <li :class="{ active: aiReviewPhase === 'refresh', done: aiReviewPhase !== 'refresh' }">刷新当前行情</li>
              <li :class="{ active: aiReviewPhase === 'history', done: aiReviewPhase === 'analysis' }">补齐近 90 天行情</li>
              <li :class="{ active: aiReviewPhase === 'analysis' }">生成结构化复盘</li>
            </ol>
            <div v-if="aiReviewError" class="ai-error"><p>{{ aiReviewError }}</p><el-button plain @click="runAIReview">重新复盘</el-button></div>
            <div v-if="aiReview" class="ai-result">
              <div class="ai-result__summary"><span>{{ aiActionLabel }}</span><strong>{{ aiReview.summary }}</strong><small>可信程度：{{ aiConfidenceLabel }}</small></div>
              <section><h3>主要依据</h3><ul><li v-for="(reason, index) in aiReview.reasons" :key="`reason-${index}`"><p>{{ reason.text }}</p><small v-for="fact in reason.facts" :key="fact.fact_id">{{ fact.label }}：{{ fact.value ?? '未知' }}</small></li></ul></section>
              <section v-if="aiReview.risk_scenarios?.length"><h3>风险情景</h3><ul><li v-for="(scenario, index) in aiReview.risk_scenarios" :key="`scenario-${index}`"><strong>{{ scenario.condition }}</strong><p>{{ scenario.impact }}</p></li></ul></section>
              <section><h3>数据局限</h3><ul><li v-for="item in aiReview.limitations" :key="item">{{ item }}</li></ul></section>
              <p class="ai-meta">行情 {{ formatTime(aiReview.current_quote_at) }} · 历史截至 {{ aiReview.history_last_trade_date }} · 生成于 {{ formatTime(aiReview.generated_at) }} · DeepSeek · {{ aiReview.model }}</p>
              <p class="ai-advisory">复盘不是收益预测或交易指令；系统不会自动修改止损、加减仓或下单。</p>
              <el-button v-if="aiReview.can_open_add_on_preview && addOnPlanningAvailable" type="primary" plain @click="openAddOnPlan">进入加仓风险试算</el-button>
            </div>
            <div class="ai-review-actions"><el-button type="primary" :loading="aiReviewLoading" @click="runAIReview">{{ aiReview ? '重新复盘' : '更新行情并 AI 复盘' }}</el-button></div>
          </template>
        </div>
      </section>

      <section class="panel" aria-labelledby="stop-settings-title">
        <header class="panel__header">
          <div><h2 id="stop-settings-title" class="panel__title">止损设置</h2><span class="panel-hint">历史最高 {{ formatAssetMoney(holding.highest_price, holding.type) }}</span></div>
          <div class="panel-actions">
            <el-button :loading="refreshing" @click="refreshPrice">刷新价格</el-button>
            <el-button v-if="addOnPlanningAvailable" @click="openAddOnPlan">加仓风险试算</el-button>
            <el-button v-if="(holding.status === 'holding' || holding.status === 'triggered') && !editMode" :type="holding.status === 'triggered' ? 'warning' : 'primary'" @click="editMode = true">{{ holding.status === 'triggered' ? '重新布防' : '修改止损' }}</el-button>
          </div>
        </header>

        <p v-if="holding.status === 'triggered'" class="rearm-hint">该持仓已触发止损。重新布防将按新规则恢复监控：若现价仍低于新止损价，将在下一监控周期再次触发；也可选择手动平仓。</p>

        <div v-if="!editMode" class="stop-settings-view">
          <div><span>止损方式</span><strong>{{ methodLabel(holding.stop_loss_method) }}</strong></div>
          <div><span>止损参数</span><strong class="number">{{ holding.stop_loss_value }}{{ holding.stop_loss_method === 'fixed' ? ' 元' : '%' }}</strong></div>
          <div><span>行情来源</span><strong>{{ holding.quote_source || '暂无' }}</strong></div>
          <div><span>行情时间</span><strong class="number">{{ formatTime(holding.quoted_at) }}</strong></div>
          <div><span>行情状态</span><strong :class="`quote-tone--${trust.tone}`">{{ trust.label }}{{ trust.actionable ? ' · 可触发' : ' · 不可触发' }}</strong></div>
        </div>

        <el-form v-else :model="editForm" label-position="top" class="edit-form" @submit.prevent="saveEdit">
          <el-form-item label="持仓名称"><el-input v-model="editForm.name" /></el-form-item>
          <el-form-item label="止损方式"><el-select v-model="editForm.stop_loss_method"><el-option label="百分比止损" value="percentage" /><el-option label="固定价格止损" value="fixed" /><el-option label="移动止损" value="trailing" /></el-select></el-form-item>
          <el-form-item :label="`止损参数（${editMeta.unit}）`"><el-input-number v-model="editForm.stop_loss_value" :precision="editMeta.precision" :step="editMeta.step" :min="editMeta.min" :controls="false" /></el-form-item>
          <p class="edit-help">{{ editMeta.help }}</p>
          <div class="edit-actions"><el-button @click="editMode = false">取消</el-button><el-button type="primary" native-type="submit" :loading="saving">保存修改</el-button></div>
        </el-form>
      </section>

      <section class="panel" aria-labelledby="stop-history-title">
        <header class="panel__header"><div><h2 id="stop-history-title" class="panel__title">止损调整记录</h2><span class="panel-hint">每次创建与修改的只读快照；删除持仓后仍保留</span></div></header>
        <div class="stop-history-body">
          <p v-if="stopHistoryError" class="history-muted">{{ stopHistoryError }}</p>
          <ol v-else-if="stopHistory.length" class="stop-history-list">
            <li v-for="entry in stopHistory" :key="entry.id">
              <span class="stop-history__tag" :class="`is-${entry.source}`">{{ entry.source === 'create' ? '创建' : '调整' }}</span>
              <strong>{{ methodLabel(entry.stop_loss_method) }} {{ entry.stop_loss_value }}{{ entry.stop_loss_method === 'fixed' ? ' 元' : '%' }}</strong>
              <span>止损价 {{ formatAssetMoney(entry.stop_loss_price, holding.type) }}</span>
              <small class="number">{{ formatTime(entry.changed_at) }}</small>
            </li>
          </ol>
          <p v-else class="history-muted">暂无止损调整记录。</p>
        </div>
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
.quote-tone--success { color: var(--color-success) !important; }
.quote-tone--warning { color: var(--color-warning) !important; }
.quote-tone--danger { color: var(--color-danger) !important; }
.quote-tone--muted { color: var(--color-text-muted) !important; }
.panel__header > div:first-child { display: grid; gap: 3px; }
.panel-actions { display: flex; gap: 8px; }
.stop-settings-view { padding: 20px; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 20px; }
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
.ai-review-body { padding: 0 20px 20px; display: grid; gap: 16px; }
.ai-empty, .ai-error { display: flex; align-items: center; justify-content: space-between; gap: 16px; color: var(--color-text-soft); }
.ai-empty p, .ai-error p { margin: 0; }
.ai-progress { margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; list-style: none; counter-reset: progress; }
.ai-progress li { min-height: 42px; padding: 10px; color: var(--color-text-muted); background: var(--color-surface-subtle); border: 1px solid var(--color-border); border-radius: 7px; font-size: 12px; }
.ai-progress li.active { color: var(--color-brand); border-color: var(--color-brand); font-weight: 700; }
.ai-progress li.done { color: var(--color-success); }
.ai-result { display: grid; gap: 16px; }
.ai-result__summary { padding-left: 14px; display: grid; gap: 5px; border-left: 4px solid var(--color-brand); }
.ai-result__summary span { color: var(--color-brand); font-size: 12px; font-weight: 700; }
.ai-result__summary strong { font-size: 18px; line-height: 1.5; }
.ai-result__summary small, .ai-meta, .ai-advisory { color: var(--color-text-muted); font-size: 11px; }
.ai-result section { display: grid; gap: 8px; }
.ai-result h3 { margin: 0; font-size: 13px; }
.ai-result ul { margin: 0; padding-left: 20px; display: grid; gap: 8px; color: var(--color-text-soft); }
.ai-result li p { margin: 0; line-height: 1.6; }
.ai-result li small { margin-right: 12px; color: var(--color-text-muted); }
.ai-meta, .ai-advisory { margin: 0; line-height: 1.7; }
.ai-review-actions { display: flex; justify-content: flex-end; }
.stop-history-body { padding: 20px; }
.stop-history-list { margin: 0; padding: 0; display: grid; gap: 10px; list-style: none; }
.stop-history-list li { padding: 12px 14px; display: flex; align-items: center; gap: 12px; background: var(--color-surface-subtle); border: 1px solid var(--color-border); border-radius: 9px; }
.stop-history-list strong { font-size: 13px; }
.stop-history-list span:not(.stop-history__tag) { color: var(--color-text-soft); font-size: 12px; }
.stop-history-list small { margin-left: auto; color: var(--color-text-muted); font-size: 11px; }
.stop-history__tag { padding: 2px 8px; border-radius: 999px; font-size: 11px; }
.stop-history__tag.is-create { color: var(--color-success); background: var(--color-success-soft); }
.stop-history__tag.is-update { color: var(--color-brand); background: var(--color-brand-soft); }
.history-muted { margin: 0; color: var(--color-text-soft); font-size: 12px; }
.rearm-hint { margin: 0 20px 0; padding: 11px 14px; color: var(--color-warning); background: var(--color-warning-soft); border: 1px solid #ecd7b5; border-radius: 9px; font-size: 12px; line-height: 1.7; }
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
  .ai-review-body { padding: 0 16px 16px; }
  .ai-empty, .ai-error { align-items: stretch; flex-direction: column; }
  .ai-progress { grid-template-columns: 1fr; }
  .ai-review-actions .el-button, .ai-result > .el-button { width: 100%; min-height: 44px; }
}
</style>
