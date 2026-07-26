<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import api from '../api'
import { useRuntimeCapabilitiesStore } from '../stores/runtimeCapabilities'
import { formatDecimal, formatMoney } from '../utils/format'

const router = useRouter()
const runtimeCapabilities = useRuntimeCapabilitiesStore()
const submitting = ref(false)
const creating = ref(false)
const result = ref(null)
const reviewOpen = ref(false)
const form = reactive({
  code: '', name: '', asset_type: 'stock', entry_price: null,
  stop_method: 'percentage', stop_value: 10,
  entry_fees: 0, estimated_exit_fees: 0, position_risk_limit_pct: null,
})

const ready = computed(() => result.value?.status === 'ready')
const planningAvailable = computed(() => (
  runtimeCapabilities.isAvailable('risk_plan_previews')
  && runtimeCapabilities.isAvailable('risk_covered_position_creation')
))
const reasonLabels = {
  portfolio_equity_unset: '请先在设置中维护组合权益。',
  portfolio_risk_coverage_incomplete: '存在没有有效止损规则的开放仓位，无法安全计算剩余风险容量。',
  portfolio_risk_capacity_exhausted: '组合风险容量已经用尽或超过上限。',
  invalid_stop_rule: '止损规则无效，请检查止损价或百分比。',
  non_positive_unit_risk: '初始止损价必须低于计划买入价。',
  invalid_position_risk_limit: '单笔风险比例必须大于零且不能超过组合风险上限。',
  fees_consume_risk_capacity: '预计费用已占满本次可用风险。',
  quantity_below_minimum_increment: '可用风险不足以支持该资产的最小建仓数量。',
}

async function preview() {
  if (!planningAvailable.value || submitting.value) return
  submitting.value = true
  reviewOpen.value = false
  try {
    const payload = { ...form }
    if (!payload.position_risk_limit_pct) delete payload.position_risk_limit_pct
    result.value = (await api.post('/risk/plans/preview', payload)).data
  } catch {
    result.value = null
  } finally {
    submitting.value = false
  }
}

async function createPosition() {
  if (!planningAvailable.value || !ready.value || creating.value) return
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
    router.push(`/holdings/${response.data.id}`)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <section aria-labelledby="planner-title">
    <div class="page-heading">
      <div><h1 id="planner-title" class="page-title">仓位规划器</h1><p class="page-subtitle">先确定最多愿意亏多少，再决定买入数量</p></div>
      <el-button v-if="planningAvailable" @click="router.push('/settings')">风险设置</el-button>
    </div>

    <section v-if="!planningAvailable" class="panel planner-unavailable" role="status">
      <strong>当前运行模式未启用仓位规划</strong>
      <p>{{ runtimeCapabilities.error || '稳定版本继续支持原有持仓与止损流程，规划器不会发起风险试算或仓位写入。' }}</p>
      <el-button type="primary" @click="router.push('/holdings')">返回持仓管理</el-button>
    </section>

    <div v-else class="planner-layout">
      <section class="panel">
        <header class="panel__header"><div><h2 class="panel__title">计划参数</h2><span class="planner-hint">试算不会创建仓位或提交订单</span></div></header>
        <el-form class="planner-form" label-position="top" @submit.prevent="preview">
          <div class="form-grid">
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
          <el-button type="primary" native-type="submit" :loading="submitting">计算建议数量</el-button>
        </el-form>
      </section>

      <section class="panel result-panel" aria-live="polite">
        <header class="panel__header"><div><h2 class="panel__title">规划结果</h2><span class="planner-hint">所有财务计算均由后端 Decimal 引擎完成</span></div></header>
        <div v-if="!result" class="result-empty">填写计划参数后开始试算。未知金额不会显示为零。</div>
        <div v-else class="result-body">
          <div v-if="!ready" class="result-warning" role="status">
            <strong>暂不能给出建议数量</strong>
            <span>{{ reasonLabels[result.reason_code] || result.reason_code }}</span>
          </div>
          <div v-else class="recommendation">
            <span>建议最大数量</span>
            <strong class="number">{{ formatDecimal(result.recommended_quantity, form.asset_type === 'stock' ? 0 : 6) }} {{ form.asset_type === 'stock' ? '股' : '份' }}</strong>
            <small>A 股按 100 股向下取整；基金按六位小数向下取整。</small>
          </div>
          <dl class="calculation-grid">
            <div><dt>初始止损价</dt><dd>{{ formatMoney(result.initial_stop_price, 4) }}</dd></div>
            <div><dt>每单位价格风险</dt><dd>{{ formatMoney(result.unit_price_risk, 4) }}</dd></div>
            <div><dt>单笔风险上限</dt><dd>{{ formatMoney(result.position_limit_amount) }}</dd></div>
            <div><dt>组合剩余容量</dt><dd>{{ formatMoney(result.remaining_portfolio_capacity) }}</dd></div>
            <div><dt>本次允许风险</dt><dd>{{ formatMoney(result.allowed_plan_risk) }}</dd></div>
            <div><dt>取整前数量</dt><dd>{{ formatDecimal(result.raw_quantity, 6) }}</dd></div>
            <div><dt>预计止损损失</dt><dd>{{ formatMoney(result.projected_loss_at_stop) }}</dd></div>
            <div><dt>预计所需资金</dt><dd>{{ formatMoney(result.required_capital) }}</dd></div>
            <div><dt>预计买入费用</dt><dd>{{ formatMoney(result.entry_fees) }}</dd></div>
            <div><dt>预计退出费用</dt><dd>{{ formatMoney(result.estimated_exit_fees) }}</dd></div>
          </dl>
          <p class="advisory">这是风险控制建议，不是收益预测或下单指令。系统不知道你的券商可用现金，所需资金必须自行核对；当前试算不会预留风险额度，也没有提交任何订单。</p>
          <el-button v-if="ready" type="primary" plain @click="reviewOpen = true">继续填写建仓确认</el-button>
        </div>
      </section>
    </div>

    <section v-if="planningAvailable && reviewOpen && ready" class="panel confirm-panel" aria-labelledby="confirm-title">
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
.planner-layout { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(360px, .95fr); gap: 16px; align-items: start; }
.planner-unavailable { padding: 24px; display: grid; justify-items: start; gap: 12px; }
.planner-unavailable p { margin: 0; color: var(--color-text-soft); line-height: 1.7; }
.planner-hint { color: var(--color-text-muted); font-size: 11px; }
.planner-form, .result-body, .result-empty { padding: 0 20px 20px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; }
.planner-form :deep(.el-input-number), .planner-form :deep(.el-select) { width: 100%; }
.result-empty { color: var(--color-text-soft); font-size: 13px; }
.result-body { display: grid; gap: 16px; }
.result-warning, .recommendation { padding: 16px; display: grid; gap: 5px; border-radius: 10px; }
.result-warning { color: var(--color-warning); background: var(--color-warning-soft); }
.recommendation { color: #f7fbf9; background: var(--color-brand); }
.recommendation strong { font-size: 28px; }
.recommendation small { color: rgba(255,255,255,.72); }
.calculation-grid { margin: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; overflow: hidden; background: var(--color-border); border: 1px solid var(--color-border); border-radius: 9px; }
.calculation-grid div { padding: 11px 12px; display: grid; gap: 4px; background: var(--color-surface); }
.calculation-grid dt { color: var(--color-text-muted); font-size: 11px; }
.calculation-grid dd { margin: 0; font-variant-numeric: tabular-nums; font-weight: 650; }
.advisory { margin: 0; color: var(--color-text-soft); font-size: 12px; line-height: 1.7; }
.confirm-panel { margin-top: 16px; }
.confirm-body { padding: 0 20px 20px; display: grid; gap: 10px; }
.confirm-body p { margin: 0; color: var(--color-text-soft); line-height: 1.6; }
.confirm-body > div { display: flex; justify-content: flex-end; gap: 8px; }
@media (max-width: 900px) { .planner-layout { grid-template-columns: 1fr; } }
@media (max-width: 767px) {
  .form-grid, .calculation-grid { grid-template-columns: 1fr; }
  .planner-form > .el-button { width: 100%; min-height: 44px; }
  .confirm-body > div { flex-direction: column-reverse; }
  .confirm-body .el-button { width: 100%; min-height: 44px; }
}
</style>
