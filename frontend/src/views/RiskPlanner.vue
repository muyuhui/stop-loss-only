<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { useRuntimeCapabilitiesStore } from '../stores/runtimeCapabilities'
import { formatDecimal, formatMoney } from '../utils/format'

const route = useRoute()
const router = useRouter()
const runtimeCapabilities = useRuntimeCapabilitiesStore()
const submitting = ref(false)
const creating = ref(false)
const result = ref(null)
const reviewOpen = ref(false)
const mode = ref('new')
const selectedHolding = ref(null)
const holdingLoading = ref(false)
const holdingError = ref('')

const form = reactive({
  code: '', name: '', asset_type: 'stock', entry_price: null,
  stop_method: 'percentage', stop_value: 10,
  entry_fees: 0, estimated_exit_fees: 0, position_risk_limit_pct: null,
})
const addOnForm = reactive({
  planned_entry_price: null,
  entry_fees: 0,
  estimated_exit_fees: 0,
  position_risk_limit_pct: null,
})

const ready = computed(() => result.value?.status === 'ready')
const planningAvailable = computed(() => runtimeCapabilities.isAvailable('risk_plan_previews'))
const creationAvailable = computed(() => runtimeCapabilities.isAvailable('risk_covered_position_creation'))
const addOnContextReady = computed(() => mode.value === 'add-on' && selectedHolding.value?.status === 'holding')
const canSubmit = computed(() => {
  if (!planningAvailable.value || submitting.value) return false
  if (mode.value === 'add-on') return addOnContextReady.value && Number(addOnForm.planned_entry_price) > 0
  return Boolean(form.code.trim() && form.name.trim() && Number(form.entry_price) > 0 && Number(form.stop_value) > 0)
})
const assetType = computed(() => mode.value === 'add-on' ? selectedHolding.value?.type : form.asset_type)

const reasonLabels = {
  portfolio_equity_unset: '请先在设置中维护组合权益。',
  portfolio_risk_coverage_incomplete: '存在无法计算止损风险的活动持仓，无法安全计算剩余风险容量。',
  portfolio_risk_capacity_exhausted: '组合风险容量已经用尽或超过上限。',
  position_risk_capacity_exhausted: '该持仓的单笔风险容量已经用尽。',
  invalid_stop_rule: '止损规则无效，请检查止损价或百分比。',
  non_positive_unit_risk: '初始止损价必须低于计划买入价。',
  entry_not_above_existing_stop: '计划成交价必须高于现有止损价。',
  invalid_position_risk_limit: '单笔风险比例必须大于零且不能超过组合风险上限。',
  fees_consume_risk_capacity: '预计费用已占满本次可用风险。',
  quantity_below_minimum_increment: '可用风险不足以支持该资产的最小买入数量。',
  holding_not_eligible: '只有正常持有中的持仓可以进行加仓风险试算。',
  holding_risk_unavailable: '当前持仓缺少可计算的成本、数量或止损价。',
}

function queryHoldingId() {
  const value = Number(route.query.holding_id)
  return Number.isInteger(value) && value > 0 ? value : null
}

async function loadHolding(id) {
  selectedHolding.value = null
  holdingError.value = ''
  if (!id) return
  holdingLoading.value = true
  try {
    selectedHolding.value = (await api.get(`/holdings/${id}`)).data
    addOnForm.planned_entry_price = (
      selectedHolding.value.is_actionable && selectedHolding.value.current_price != null
        ? Number(selectedHolding.value.current_price)
        : null
    )
  } catch {
    holdingError.value = '持仓风险上下文加载失败，请返回持仓详情重试。'
  } finally {
    holdingLoading.value = false
  }
}

function syncRoute() {
  const nextMode = route.query.mode === 'add-on' ? 'add-on' : 'new'
  const changed = mode.value !== nextMode
  mode.value = nextMode
  if (changed) {
    result.value = null
    reviewOpen.value = false
  }
  if (nextMode === 'add-on') void loadHolding(queryHoldingId())
  else selectedHolding.value = null
}

async function selectMode(nextMode) {
  const query = { mode: nextMode }
  if (nextMode === 'add-on' && queryHoldingId()) query.holding_id = String(queryHoldingId())
  await router.replace({ path: '/planner', query })
}

async function preview() {
  if (!canSubmit.value) return
  submitting.value = true
  reviewOpen.value = false
  try {
    if (mode.value === 'add-on') {
      const payload = {
        holding_id: selectedHolding.value.id,
        ...addOnForm,
      }
      if (!payload.position_risk_limit_pct) delete payload.position_risk_limit_pct
      result.value = (await api.post('/risk/plans/add-on-preview', payload)).data
    } else {
      const payload = { ...form }
      if (!payload.position_risk_limit_pct) delete payload.position_risk_limit_pct
      result.value = (await api.post('/risk/plans/preview', payload)).data
    }
  } catch {
    result.value = null
  } finally {
    submitting.value = false
  }
}

async function createPosition() {
  if (!creationAvailable.value || mode.value !== 'new' || !ready.value || creating.value) return
  creating.value = true
  const normalized = result.value.normalized_input
  try {
    const response = await api.post('/positions', {
      code: normalized.code,
      name: normalized.name,
      asset_type: normalized.asset_type,
      quantity: result.value.recommended_quantity,
      unit_cost: normalized.entry_price,
      fees: result.value.entry_fees,
      taxes: '0',
      stop_method: normalized.stop_method,
      stop_value: normalized.stop_value,
    })
    ElMessage.success('仓位已创建，风险预算将按实际仓位重新计算')
    await router.push(`/holdings/${response.data.id}`)
  } finally {
    creating.value = false
  }
}

function calculatedTime(value) {
  if (!value) return '--'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

watch(() => [route.query.mode, route.query.holding_id], syncRoute)
onMounted(syncRoute)
</script>

<template>
  <section aria-labelledby="planner-title">
    <div class="page-heading">
      <div><h1 id="planner-title" class="page-title">风险试算</h1><p class="page-subtitle">先确定最多愿意亏多少，再计算风险约束下的最大数量</p></div>
      <el-button v-if="planningAvailable" @click="router.push('/settings')">风险设置</el-button>
    </div>

    <section v-if="!planningAvailable" class="panel planner-unavailable" role="status">
      <strong>当前运行模式未启用风险试算</strong>
      <p>{{ runtimeCapabilities.error || '核心持仓与止损流程仍可继续使用；此页面不会发起试算或任何仓位写入。' }}</p>
      <el-button type="primary" @click="router.push('/holdings')">返回持仓管理</el-button>
    </section>

    <template v-else>
      <div class="mode-switch" role="tablist" aria-label="风险试算模式">
        <button type="button" role="tab" :aria-selected="mode === 'new'" :class="{ 'is-active': mode === 'new' }" @click="selectMode('new')">新仓试算</button>
        <button type="button" role="tab" :aria-selected="mode === 'add-on'" :class="{ 'is-active': mode === 'add-on' }" @click="selectMode('add-on')">加仓试算</button>
      </div>

      <div class="planner-layout">
        <section class="panel">
          <header class="panel__header"><div><h2 class="panel__title">{{ mode === 'new' ? '新仓计划参数' : '加仓计划参数' }}</h2><span class="planner-hint">试算不会修改持仓、预留额度或提交订单</span></div></header>

          <div v-if="mode === 'add-on' && holdingLoading" class="context-state">正在加载持仓风险上下文...</div>
          <div v-else-if="mode === 'add-on' && !selectedHolding" class="context-state">
            <strong>{{ holdingError || '请从正常持有中的持仓详情进入加仓试算。' }}</strong>
            <el-button @click="router.push('/holdings')">选择持仓</el-button>
          </div>

          <el-form v-else class="planner-form" label-position="top" @submit.prevent="preview">
            <div v-if="mode === 'add-on'" class="holding-context" aria-label="加仓持仓上下文">
              <div><span>持仓</span><strong>{{ selectedHolding.name }}（{{ selectedHolding.code }}）</strong></div>
              <div><span>现有数量</span><strong class="number">{{ selectedHolding.quantity }} {{ selectedHolding.type === 'stock' ? '股' : '份' }}</strong></div>
              <div><span>买入成本</span><strong class="number">{{ formatMoney(selectedHolding.buy_price, 4) }}</strong></div>
              <div><span>保留止损价</span><strong class="number">{{ formatMoney(selectedHolding.stop_loss_price, 4) }}</strong></div>
              <small>本次试算不会降低止损价，也不会重置移动止损最高价。</small>
            </div>

            <div v-if="mode === 'new'" class="form-grid">
              <el-form-item label="资产类型"><el-radio-group v-model="form.asset_type"><el-radio value="stock">A 股</el-radio><el-radio value="fund">基金</el-radio></el-radio-group></el-form-item>
              <el-form-item label="代码"><el-input v-model="form.code" aria-label="计划标的代码" placeholder="例如 000001" /></el-form-item>
              <el-form-item label="名称"><el-input v-model="form.name" aria-label="计划标的名称" placeholder="例如 平安银行" /></el-form-item>
              <el-form-item label="计划买入价"><el-input-number v-model="form.entry_price" :min="0.0001" :step="0.0001" :precision="4" :controls="false" aria-label="计划买入价" /></el-form-item>
              <el-form-item label="止损方式"><el-select v-model="form.stop_method" aria-label="止损方式"><el-option label="固定价格" value="fixed" /><el-option label="百分比" value="percentage" /><el-option label="移动止损" value="trailing" /></el-select></el-form-item>
              <el-form-item label="止损参数"><el-input-number v-model="form.stop_value" :min="0.0001" :step="0.0001" :precision="4" :controls="false" aria-label="止损参数" /></el-form-item>
              <el-form-item label="预计买入费用"><el-input-number v-model="form.entry_fees" :min="0" :step="0.01" :precision="2" :controls="false" aria-label="预计买入费用" /></el-form-item>
              <el-form-item label="预计退出费用"><el-input-number v-model="form.estimated_exit_fees" :min="0" :step="0.01" :precision="2" :controls="false" aria-label="预计退出费用" /></el-form-item>
              <el-form-item label="单笔风险比例（可选）"><el-input-number v-model="form.position_risk_limit_pct" :min="0.01" :max="100" :step="0.01" :precision="2" :controls="false" aria-label="本次单笔风险比例" /></el-form-item>
            </div>

            <div v-else class="form-grid">
              <el-form-item label="计划成交价"><el-input-number v-model="addOnForm.planned_entry_price" :min="0.0001" :step="0.0001" :precision="4" :controls="false" aria-label="计划加仓成交价" /></el-form-item>
              <el-form-item label="预计买入费用"><el-input-number v-model="addOnForm.entry_fees" :min="0" :step="0.01" :precision="2" :controls="false" aria-label="加仓预计买入费用" /></el-form-item>
              <el-form-item label="预计退出费用"><el-input-number v-model="addOnForm.estimated_exit_fees" :min="0" :step="0.01" :precision="2" :controls="false" aria-label="加仓预计退出费用" /></el-form-item>
              <el-form-item label="单笔风险比例（可选）"><el-input-number v-model="addOnForm.position_risk_limit_pct" :min="0.01" :max="100" :step="0.01" :precision="2" :controls="false" aria-label="加仓单笔风险比例" /></el-form-item>
            </div>
            <el-button type="primary" native-type="submit" :disabled="!canSubmit" :loading="submitting">计算风险上限</el-button>
          </el-form>
        </section>

        <section class="panel result-panel" aria-live="polite">
          <header class="panel__header"><div><h2 class="panel__title">试算结果</h2><span class="planner-hint">所有财务计算均由后端 Decimal 引擎完成</span></div></header>
          <div v-if="!result" class="result-empty">填写计划参数后开始试算。未知金额不会显示为零。</div>
          <div v-else class="result-body">
            <div v-if="!ready" class="result-warning" role="status">
              <strong>暂不能给出风险上限数量</strong>
              <span>{{ reasonLabels[result.reason_code] || result.reason_code }}</span>
            </div>
            <div v-else class="recommendation">
              <span>风险约束下的最大数量</span>
              <strong class="number">{{ formatDecimal(result.recommended_quantity, assetType === 'stock' ? 0 : 6) }} {{ assetType === 'stock' ? '股' : '份' }}</strong>
              <small>这是上限而不是买满建议；可以选择更小数量。</small>
            </div>

            <dl v-if="mode === 'new'" class="calculation-grid">
              <div><dt>初始止损价</dt><dd>{{ formatMoney(result.initial_stop_price, 4) }}</dd></div>
              <div><dt>每单位价格风险</dt><dd>{{ formatMoney(result.unit_price_risk, 4) }}</dd></div>
              <div><dt>单笔风险上限</dt><dd>{{ formatMoney(result.position_limit_amount) }}</dd></div>
              <div><dt>组合剩余容量</dt><dd>{{ formatMoney(result.remaining_portfolio_capacity) }}</dd></div>
              <div><dt>本次允许风险</dt><dd>{{ formatMoney(result.allowed_plan_risk) }}</dd></div>
              <div><dt>取整前数量</dt><dd>{{ formatDecimal(result.raw_quantity, 6) }}</dd></div>
              <div><dt>预计止损损失</dt><dd>{{ formatMoney(result.projected_loss_at_stop) }}</dd></div>
              <div><dt>预计所需资金</dt><dd>{{ formatMoney(result.required_capital) }}</dd></div>
              <div><dt>试算后组合风险</dt><dd>{{ formatMoney(result.post_plan_portfolio_used_risk) }}</dd></div>
              <div><dt>试算后预算使用率</dt><dd>{{ result.post_plan_portfolio_utilization_pct ?? '--' }}%</dd></div>
            </dl>

            <dl v-else class="calculation-grid">
              <div><dt>计划成交价</dt><dd>{{ formatMoney(result.planned_entry_price, 4) }}</dd></div>
              <div><dt>保留止损价</dt><dd>{{ formatMoney(result.existing_stop_price, 4) }}</dd></div>
              <div><dt>当前持仓风险</dt><dd>{{ formatMoney(result.current_holding_risk) }}</dd></div>
              <div><dt>单笔剩余容量</dt><dd>{{ formatMoney(result.remaining_position_capacity) }}</dd></div>
              <div><dt>组合剩余容量</dt><dd>{{ formatMoney(result.remaining_portfolio_capacity) }}</dd></div>
              <div><dt>允许增量风险</dt><dd>{{ formatMoney(result.allowed_incremental_risk) }}</dd></div>
              <div><dt>每单位价格风险</dt><dd>{{ formatMoney(result.unit_price_risk, 4) }}</dd></div>
              <div><dt>取整前数量</dt><dd>{{ formatDecimal(result.raw_quantity, 6) }}</dd></div>
              <div><dt>增量预计损失</dt><dd>{{ formatMoney(result.incremental_projected_loss) }}</dd></div>
              <div><dt>试算后持仓风险</dt><dd>{{ formatMoney(result.post_plan_holding_risk) }}</dd></div>
              <div><dt>试算后组合风险</dt><dd>{{ formatMoney(result.post_plan_portfolio_used_risk) }}</dd></div>
              <div><dt>试算后预算使用率</dt><dd>{{ result.post_plan_portfolio_utilization_pct ?? '--' }}%</dd></div>
              <div><dt>预计所需资金</dt><dd>{{ formatMoney(result.required_capital) }}</dd></div>
            </dl>

            <p class="calculated-at">试算时间：{{ calculatedTime(result.calculated_at) }}</p>
            <p class="advisory">这是风险承受能力试算，不判断标的质量或上涨概率，不是收益预测、买入建议或下单指令。系统不知道你的券商可用现金，结果不会预留风险额度，没有提交任何订单，也不会记录实际加仓。</p>
            <el-button v-if="creationAvailable && mode === 'new' && ready" type="primary" plain @click="reviewOpen = true">继续填写建仓确认</el-button>
          </div>
        </section>
      </div>
    </template>

    <section v-if="planningAvailable && creationAvailable && mode === 'new' && reviewOpen && ready" class="panel confirm-panel" aria-labelledby="confirm-title">
      <header class="panel__header"><div><h2 id="confirm-title" class="panel__title">确认创建仓位</h2><span class="planner-hint">这是独立业务提交；请再次检查最新资金与风险状态</span></div></header>
      <div class="confirm-body">
        <p>{{ result.normalized_input.name }}（{{ result.normalized_input.code }}），{{ result.recommended_quantity }} {{ form.asset_type === 'stock' ? '股' : '份' }}，成本价 {{ result.normalized_input.entry_price }}，止损 {{ result.initial_stop_price }}。</p>
        <p>风险容量不会因试算而锁定；提交时以正常仓位创建校验为准。</p>
        <div><el-button @click="reviewOpen = false">返回修改</el-button><el-button type="primary" :loading="creating" @click="createPosition">确认创建仓位</el-button></div>
      </div>
    </section>
  </section>
</template>

<style scoped>
.mode-switch { width: fit-content; margin-bottom: 16px; padding: 3px; display: grid; grid-template-columns: repeat(2, minmax(108px, 1fr)); gap: 3px; background: var(--color-surface-subtle); border: 1px solid var(--color-border); border-radius: 8px; }
.mode-switch button { min-height: 38px; padding: 0 14px; color: var(--color-text-soft); background: transparent; border: 0; border-radius: 6px; cursor: pointer; }
.mode-switch button.is-active { color: #fff; background: var(--color-brand); font-weight: 700; }
.planner-layout { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(360px, .95fr); gap: 16px; align-items: start; }
.planner-unavailable { padding: 24px; display: grid; justify-items: start; gap: 12px; }
.planner-unavailable p { margin: 0; color: var(--color-text-soft); line-height: 1.7; }
.planner-hint { color: var(--color-text-muted); font-size: 11px; }
.planner-form, .result-body, .result-empty, .context-state { padding: 0 20px 20px; }
.context-state { display: grid; justify-items: start; gap: 12px; color: var(--color-text-soft); }
.holding-context { margin-bottom: 18px; padding: 14px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; background: var(--color-surface-subtle); border-radius: 8px; }
.holding-context div { display: grid; gap: 4px; }
.holding-context span, .holding-context small { color: var(--color-text-muted); font-size: 11px; }
.holding-context small { grid-column: 1 / -1; line-height: 1.6; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; }
.planner-form :deep(.el-input-number), .planner-form :deep(.el-select) { width: 100%; }
.result-empty { color: var(--color-text-soft); font-size: 13px; }
.result-body { display: grid; gap: 16px; }
.result-warning, .recommendation { padding: 16px; display: grid; gap: 5px; border-radius: 8px; }
.result-warning { color: var(--color-warning); background: var(--color-warning-soft); }
.recommendation { color: #f7fbf9; background: var(--color-brand); }
.recommendation strong { font-size: 28px; }
.recommendation small { color: rgba(255,255,255,.75); }
.calculation-grid { margin: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; overflow: hidden; background: var(--color-border); border: 1px solid var(--color-border); border-radius: 8px; }
.calculation-grid div { padding: 11px 12px; display: grid; gap: 4px; background: var(--color-surface); }
.calculation-grid dt { color: var(--color-text-muted); font-size: 11px; }
.calculation-grid dd { margin: 0; font-variant-numeric: tabular-nums; font-weight: 650; }
.calculated-at, .advisory { margin: 0; color: var(--color-text-soft); font-size: 12px; line-height: 1.7; }
.confirm-panel { margin-top: 16px; }
.confirm-body { padding: 0 20px 20px; display: grid; gap: 10px; }
.confirm-body p { margin: 0; color: var(--color-text-soft); line-height: 1.6; }
.confirm-body > div { display: flex; justify-content: flex-end; gap: 8px; }
@media (max-width: 900px) { .planner-layout { grid-template-columns: 1fr; } }
@media (max-width: 767px) {
  .mode-switch { width: 100%; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .form-grid, .calculation-grid, .holding-context { grid-template-columns: 1fr; }
  .holding-context small { grid-column: 1; }
  .planner-form > .el-button { width: 100%; min-height: 44px; }
  .confirm-body > div { flex-direction: column-reverse; }
  .confirm-body .el-button { width: 100%; min-height: 44px; }
}
</style>
