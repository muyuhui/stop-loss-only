<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import DataState from '../components/DataState.vue'
import { useSettingsStore } from '../stores/settings'
import { useRiskBudgetStore } from '../stores/riskBudget'
import { useRuntimeCapabilitiesStore } from '../stores/runtimeCapabilities'
import { dashboardRiskSummary, sortHoldingsByRisk } from '../utils/dashboard'
import { formatAssetMoney, formatMoney, formatSignedPercent, formatTime, stopLossRisk, valueTone } from '../utils/format'
import { holdingStatusLabel, holdingStatusTag } from '../utils/holdingStatus'
import { formatMarketSession, formatQuoteFreshness, quoteFreshnessText } from '../utils/market'
import { createPoller } from '../utils/poller'
import { useRequestState } from '../utils/requestState'
import { monitoringTrust, quoteTrust } from '../utils/quoteTrust'

const emptyDashboard = {
  active_cost: 0, active_market_value: 0, unrealized_profit_loss: 0,
  unrealized_profit_loss_pct: 0, realized_profit_loss: 0,
  month_summary: null,
  holding_count: 0, triggered_count: 0, closed_count: 0, active_alerts_count: 0,
  today_alert_count: 0, latest_alert: null, holdings: [],
}

const dashboard = ref(emptyDashboard)
const monitoring = ref(null)
const settingsStore = useSettingsStore()
const riskBudgetStore = useRiskBudgetStore()
const runtimeCapabilities = useRuntimeCapabilitiesStore()
const request = useRequestState()
const router = useRouter()
const poller = createPoller(load)

const risk = computed(() => dashboardRiskSummary(dashboard.value))
const sortedHoldings = computed(() => sortHoldingsByRisk(dashboard.value.holdings))
const triggeredHoldings = computed(() => sortedHoldings.value.filter((row) => row.status === 'triggered'))
const isStale = computed(() => request.isStale(settingsStore.pollInterval))
const monitoringSummary = computed(() => monitoringTrust(monitoring.value || {}))
const budget = computed(() => riskBudgetStore.data)
const riskPlanningAvailable = computed(() => runtimeCapabilities.isAvailable('risk_budget_reads'))
const actionableCoverage = computed(() => (
  monitoring.value?.actionable_quote_coverage_pct
  ?? dashboard.value.actionable_position_coverage_pct
  ?? null
))
const valuationCoverage = computed(() => (
  monitoring.value?.valuation_quote_coverage_pct
  ?? dashboard.value.valuation_coverage_pct
  ?? null
))
const activeHoldingCount = computed(() => dashboard.value.holding_count + dashboard.value.triggered_count)

function coverageLabel(value) {
  if (value !== null && value !== undefined) return `${value}%`
  return activeHoldingCount.value === 0 ? '暂无活动持仓' : '不可用'
}

async function load() {
  request.begin()
  try {
    const budgetRequest = riskPlanningAvailable.value
      ? riskBudgetStore.fetchBudget()
      : Promise.resolve(false)
    const [res, trustResponse] = await Promise.all([
      api.get('/dashboard'),
      api.get('/monitoring/status').catch(() => null),
      budgetRequest,
    ])
    dashboard.value = res.data
    if (trustResponse) monitoring.value = trustResponse.data
    request.succeed()
  } catch {
    request.fail('仪表盘刷新失败，当前展示的是最后一次成功数据。')
  }
}

function startPolling() {
  poller.start(settingsStore.pollInterval)
}

onMounted(async () => {
  await settingsStore.fetchSettings()
  await load()
  startPolling()
})

watch(() => settingsStore.pollInterval, startPolling)
watch(riskPlanningAvailable, (available) => {
  if (available && !riskBudgetStore.data && !riskBudgetStore.loading) void riskBudgetStore.fetchBudget()
})
onUnmounted(() => poller.stop())
</script>

<template>
  <section aria-labelledby="dashboard-title">
    <div class="page-heading">
      <div>
        <h1 id="dashboard-title" class="page-title">仪表盘</h1>
        <p class="page-subtitle">先看风险，再看组合表现</p>
      </div>
      <div class="heading-actions">
        <span v-if="request.lastUpdatedAt.value" class="updated-at">
          更新于 {{ formatTime(request.lastUpdatedAt.value) }}
        </span>
        <el-button :loading="request.refreshing.value" @click="load">刷新</el-button>
      </div>
    </div>

    <DataState
      v-if="request.initialLoading.value"
      kind="loading"
      title="正在整理组合风险"
      description="首次加载完成后将显示最新持仓和告警。"
    />
    <DataState
      v-else-if="request.error.value && !request.hasData.value"
      kind="error"
      title="暂时无法加载仪表盘"
      :description="request.error.value"
      action-label="重新加载"
      @action="load"
    />

    <div v-else class="dashboard-stack">
      <div v-if="request.error.value || isStale" class="status-strip is-warning" role="status">
        <span>{{ request.error.value || '数据可能已经过期，请手动刷新。' }}</span>
        <el-button size="small" link @click="load">重试</el-button>
      </div>

      <div class="monitoring-trust" :class="`monitoring-trust--${monitoringSummary.tone}`" role="status">
        <strong>{{ monitoringSummary.title }}</strong>
        <span>{{ monitoringSummary.detail }}</span>
        <span v-if="formatMarketSession(monitoring?.market_session)" class="session-badge">{{ formatMarketSession(monitoring?.market_session) }}</span>
      </div>

      <div class="coverage-summary" aria-label="行情覆盖率">
        <span>可操作行情覆盖：<strong>{{ coverageLabel(actionableCoverage) }}</strong></span>
        <span>估值行情覆盖：<strong>{{ coverageLabel(valuationCoverage) }}</strong></span>
        <el-button link @click="router.push('/holdings')">查看风险持仓</el-button>
      </div>

      <section v-if="riskPlanningAvailable" class="panel risk-budget-panel" aria-labelledby="risk-budget-title">
        <header class="panel__header">
          <div><h2 id="risk-budget-title" class="panel__title">风险预算</h2><span class="section-hint">按所有活动持仓触及止损时的预计损失统计，与行情估值覆盖分开计算</span></div>
          <el-button v-if="runtimeCapabilities.isAvailable('risk_plan_previews')" type="primary" link @click="router.push('/planner')">新仓风险试算</el-button>
        </header>
        <div v-if="budget" class="risk-budget-grid">
          <article><span>组合风险上限</span><strong class="number">{{ formatMoney(budget.portfolio_limit_amount) }}</strong><small>手工权益 {{ formatMoney(budget.portfolio_equity) }} × {{ budget.portfolio_risk_limit_pct }}%</small></article>
          <article><span>已使用风险</span><strong class="number">{{ formatMoney(budget.used_risk_amount) }}</strong><small>覆盖 {{ budget.covered_position_count }}/{{ budget.open_position_count }} 个活动持仓</small></article>
          <article>
            <span>{{ budget.remaining_capacity === null ? '剩余风险容量未知' : '剩余风险容量' }}</span>
            <strong class="number">{{ formatMoney(budget.remaining_capacity) }}</strong>
            <small v-if="budget.status === 'incomplete'">存在无法计算止损风险的活动持仓，不能安全估算剩余额度</small>
            <small v-else-if="budget.status === 'exceeded'">已超过上限 {{ formatMoney(budget.exceeded_amount) }}</small>
            <small v-else>预算使用率 {{ budget.utilization_pct ?? '--' }}%</small>
            <el-button v-if="budget.status === 'incomplete'" link @click="router.push('/holdings')">查看未覆盖仓位</el-button>
          </article>
        </div>
        <div v-else class="risk-budget-unavailable">
          <strong>{{ riskPlanningAvailable ? '风险预算暂时不可用' : '当前运行模式未启用风险预算' }}</strong>
          <span v-if="runtimeCapabilities.error">{{ runtimeCapabilities.error }}</span>
          <span v-else-if="!riskPlanningAvailable">当前稳定版本继续使用原有持仓与止损流程，不会请求尚未启用的风险接口。</span>
          <span v-else>请稍后重试；未知值不会显示为零。</span>
          <el-button v-if="riskPlanningAvailable" link @click="router.push('/settings')">前往设置</el-button>
        </div>
      </section>

      <section class="risk-hero" :class="`risk-hero--${risk.level}`" aria-labelledby="risk-title">
        <div>
          <span class="risk-hero__eyebrow">组合风险</span>
          <h2 id="risk-title" class="risk-hero__title">{{ risk.title }}</h2>
          <p class="risk-hero__description">{{ risk.description }}</p>
        </div>
        <div class="risk-hero__actions">
          <div class="risk-hero__count number">
            <strong>{{ dashboard.active_alerts_count }}</strong>
            <span>未读告警</span>
          </div>
          <el-button v-if="dashboard.active_alerts_count" type="warning" plain @click="router.push('/alerts')">
            查看告警
          </el-button>
        </div>
      </section>

      <section v-if="dashboard.month_summary" class="panel month-ledger" aria-labelledby="month-ledger-title">
        <header class="panel__header">
          <div>
            <h2 id="month-ledger-title" class="panel__title">本月账本</h2>
            <span class="section-hint">{{ dashboard.month_summary.month }} · 已实现与浮亏分开计算，不合并</span>
          </div>
        </header>
        <div class="month-ledger__grid">
          <article class="month-ledger__primary">
            <span>本月已实现盈亏</span>
            <strong class="number" :class="`tone-${valueTone(dashboard.month_summary.realized_profit_loss)}`">
              {{ formatMoney(dashboard.month_summary.realized_profit_loss) }}
            </strong>
            <small>平仓 {{ dashboard.month_summary.closed_count }} 笔</small>
          </article>
          <article class="month-ledger__stats">
            <span>本月触发 <strong class="number">{{ dashboard.month_summary.triggered_count }}</strong> 次</span>
            <span>调整止损 <strong class="number">{{ dashboard.month_summary.stop_adjustment_count }}</strong> 次（调低 {{ dashboard.month_summary.stop_lowered_count }}）</span>
          </article>
          <article v-if="dashboard.month_summary.largest_loss" class="month-ledger__stats">
            <span>最大亏损来源：<strong>{{ dashboard.month_summary.largest_loss.name }}</strong>（{{ dashboard.month_summary.largest_loss.code }}）<strong class="number" :class="`tone-${valueTone(dashboard.month_summary.largest_loss.profit_loss_amount)}`">{{ formatMoney(dashboard.month_summary.largest_loss.profit_loss_amount) }}</strong></span>
          </article>
          <article class="month-ledger__actions">
            <span class="month-ledger__reference">当前浮亏（快照）<strong class="number" :class="`tone-${valueTone(dashboard.unrealized_profit_loss)}`">{{ formatMoney(dashboard.unrealized_profit_loss) }}</strong></span>
            <el-button v-if="dashboard.triggered_count" type="warning" plain @click="router.push('/alerts')">去处置</el-button>
            <span v-else class="month-ledger__ok">无待处置</span>
          </article>
        </div>
      </section>

      <section v-if="triggeredHoldings.length" class="panel disposition-queue" aria-labelledby="disposition-title">
        <header class="panel__header">
          <div><h2 id="disposition-title" class="panel__title">待处置持仓</h2><span class="section-hint">{{ triggeredHoldings.length }} 笔已触发止损，请确认处置（重新布防或平仓）</span></div>
          <el-button type="warning" plain link @click="router.push('/alerts')">查看告警</el-button>
        </header>
        <div class="disposition-grid">
          <article v-for="row in triggeredHoldings" :key="row.id" class="disposition-card">
            <div class="disposition-card__identity"><strong>{{ row.name }}</strong><small>{{ row.code }}</small></div>
            <span>当前价 <strong class="number">{{ formatAssetMoney(row.current_price, row.type) }}</strong></span>
            <span>止损价 <strong class="number">{{ formatAssetMoney(row.stop_loss_price, row.type) }}</strong></span>
            <el-button type="warning" plain @click="router.push(`/holdings/${row.id}`)">去处置</el-button>
          </article>
        </div>
      </section>

      <section class="metric-grid" aria-label="资产摘要">
        <article class="metric-card metric-card--primary">
          <span class="metric-card__label">未实现盈亏</span>
          <strong class="metric-card__value number" :class="`tone-${valueTone(dashboard.unrealized_profit_loss)}`">
            {{ formatMoney(dashboard.unrealized_profit_loss) }}
          </strong>
          <span class="metric-card__meta number" :class="`tone-${valueTone(dashboard.unrealized_profit_loss_pct)}`">
            {{ formatSignedPercent(dashboard.unrealized_profit_loss_pct) }}
          </span>
        </article>
        <article class="metric-card">
          <span class="metric-card__label">活动市值</span>
          <strong class="metric-card__value number">{{ formatMoney(dashboard.active_market_value) }}</strong>
          <span class="metric-card__meta">{{ dashboard.holding_count + dashboard.triggered_count }} 个活动持仓</span>
        </article>
        <article class="metric-card">
          <span class="metric-card__label">活动成本</span>
          <strong class="metric-card__value number">{{ formatMoney(dashboard.active_cost) }}</strong>
          <span class="metric-card__meta">已关闭 {{ dashboard.closed_count }} 个</span>
        </article>
        <article class="metric-card">
          <span class="metric-card__label">已实现盈亏（毛）</span>
          <strong class="metric-card__value number" :class="`tone-${valueTone(dashboard.realized_profit_loss)}`">
            {{ formatMoney(dashboard.realized_profit_loss) }}
          </strong>
          <span class="metric-card__meta">已关闭持仓的毛盈亏，不含费用</span>
        </article>
      </section>

      <section class="panel" aria-labelledby="holdings-overview-title">
        <header class="panel__header">
          <div>
            <h2 id="holdings-overview-title" class="panel__title">持仓风险排序</h2>
            <span class="section-hint">距止损越近越靠前</span>
          </div>
          <el-button type="primary" link @click="router.push('/holdings')">管理持仓</el-button>
        </header>

        <DataState
          v-if="!sortedHoldings.length"
          title="还没有活动持仓"
          description="新增持仓后，这里会优先展示最接近止损的项目。"
          action-label="新增持仓"
          @action="router.push('/holdings')"
        />

        <div v-else class="desktop-only holdings-table-wrap">
          <el-table :data="sortedHoldings" @row-click="row => router.push(`/holdings/${row.id}`)">
            <el-table-column label="持仓" min-width="190">
              <template #default="{ row }">
                <div class="holding-identity"><strong>{{ row.name }}</strong><span>{{ row.code }}</span></div>
              </template>
            </el-table-column>
            <el-table-column label="当前表现" min-width="155">
              <template #default="{ row }">
                <div class="cell-stack number"><strong>{{ row.current_price == null ? '未定价' : formatAssetMoney(row.current_price, row.type) }}</strong><span :class="`quote-tone--${quoteTrust(row).tone}`">{{ quoteTrust(row).text }}</span><span class="quote-freshness">{{ quoteFreshnessText(row.quoted_at) }}</span></div>
              </template>
            </el-table-column>
            <el-table-column label="止损风险" min-width="190">
              <template #default="{ row }">
                <div class="cell-stack number"><strong>{{ formatAssetMoney(row.stop_loss_price, row.type) }}</strong><span :class="`risk-text--${stopLossRisk(row.stop_loss_distance_pct, row.status).level}`">{{ stopLossRisk(row.stop_loss_distance_pct, row.status).label }} · {{ formatSignedPercent(row.stop_loss_distance_pct) }}</span></div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }"><el-tag :type="holdingStatusTag(row.status)">{{ holdingStatusLabel(row.status) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="操作" width="90">
              <template #default="{ row }"><el-button type="primary" link @click.stop="router.push(`/holdings/${row.id}`)">详情</el-button></template>
            </el-table-column>
          </el-table>
        </div>

        <div v-if="sortedHoldings.length" class="mobile-only mobile-holding-list">
          <button v-for="row in sortedHoldings" :key="row.id" class="holding-card" type="button" @click="router.push(`/holdings/${row.id}`)">
            <span class="holding-card__header"><span><strong>{{ row.name }}</strong><small>{{ row.code }} · {{ formatQuoteFreshness(row.quoted_at) || '未定价' }}</small></span><el-tag :type="holdingStatusTag(row.status)" size="small">{{ holdingStatusLabel(row.status) }}</el-tag></span>
            <span class="holding-card__grid">
              <span><small>当前价 · {{ quoteTrust(row).label }}</small><strong class="number">{{ row.current_price == null ? '未定价' : formatAssetMoney(row.current_price, row.type) }}</strong></span>
              <span><small>盈亏</small><strong class="number" :class="`tone-${valueTone(row.profit_loss_pct)}`">{{ formatSignedPercent(row.profit_loss_pct) }}</strong></span>
              <span><small>止损价</small><strong class="number">{{ formatAssetMoney(row.stop_loss_price, row.type) }}</strong></span>
              <span><small>距止损</small><strong class="number" :class="`risk-text--${stopLossRisk(row.stop_loss_distance_pct, row.status).level}`">{{ formatSignedPercent(row.stop_loss_distance_pct) }}</strong></span>
            </span>
            <span class="holding-card__risk" :class="`risk-text--${stopLossRisk(row.stop_loss_distance_pct, row.status).level}`">{{ stopLossRisk(row.stop_loss_distance_pct, row.status).label }}</span>
          </button>
        </div>
      </section>

      <section class="today-alert" :class="{ 'today-alert--active': dashboard.latest_alert }" aria-label="今日告警摘要">
        <div>
          <strong>{{ dashboard.latest_alert ? `今日 ${dashboard.today_alert_count} 条告警` : '今日暂无告警' }}</strong>
          <span v-if="dashboard.latest_alert">
            最新：{{ dashboard.latest_alert.holding_name }}（{{ dashboard.latest_alert.holding_code }}），当前 {{ formatMoney(dashboard.latest_alert.current_price) }} / 止损 {{ formatMoney(dashboard.latest_alert.trigger_price) }}
          </span>
          <span v-else>监控仍在运行，有新告警时会在这里显示。</span>
        </div>
        <el-button v-if="dashboard.latest_alert" link @click="router.push('/alerts')">查看历史</el-button>
      </section>
    </div>
  </section>
</template>

<style scoped>
.heading-actions { display: flex; align-items: center; gap: 12px; }
.updated-at { color: var(--color-text-muted); font-size: 12px; }
.dashboard-stack { display: grid; gap: 16px; }
.monitoring-trust { padding: 11px 14px; display: flex; align-items: center; justify-content: space-between; gap: 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 9px; font-size: 12px; }
.monitoring-trust span { color: var(--color-text-soft); }
.session-badge { padding: 2px 9px; color: var(--color-brand); background: var(--color-brand-soft); border: 1px solid var(--color-brand); border-radius: 999px; font-size: 11px; font-weight: 650; }
.quote-freshness { color: var(--color-text-muted); font-size: 11px; }
.disposition-queue { border-color: #ecd7b5; }
.month-ledger__grid { padding: 0 20px 20px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.month-ledger__primary { display: grid; gap: 4px; }
.month-ledger__primary span, .month-ledger__stats span, .month-ledger__reference { color: var(--color-text-soft); font-size: 12px; }
.month-ledger__primary strong { font-size: 28px; line-height: 1.2; }
.month-ledger__primary small { color: var(--color-text-muted); font-size: 12px; }
.month-ledger__stats { display: flex; flex-wrap: wrap; align-content: center; gap: 6px 18px; }
.month-ledger__stats strong { color: var(--color-text); }
.month-ledger__actions { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; padding-top: 12px; border-top: 1px solid var(--color-border); }
.month-ledger__ok { color: var(--color-text-soft); font-size: 12px; }
@media (max-width: 767px) { .month-ledger__grid { grid-template-columns: 1fr; } }
.disposition-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; padding: 0 20px 20px; }
.disposition-card { padding: 14px; display: grid; gap: 8px; background: var(--color-warning-soft); border: 1px solid #ecd7b5; border-radius: 10px; }
.disposition-card__identity { display: grid; gap: 2px; }
.disposition-card__identity small { color: var(--color-text-muted); font-size: 11px; }
.disposition-card span:not(.disposition-card__identity) { display: flex; justify-content: space-between; gap: 8px; color: var(--color-text-soft); font-size: 12px; }
.disposition-card .el-button { justify-self: end; }
.monitoring-trust--success { border-left: 4px solid var(--color-success); }
.monitoring-trust--warning { border-left: 4px solid var(--color-warning); }
.monitoring-trust--danger { border-left: 4px solid var(--color-danger); }
.monitoring-trust--muted { border-left: 4px solid var(--color-text-muted); }
.coverage-summary { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; padding: 10px 14px; color: var(--color-text-soft); background: var(--color-bg-soft); border-radius: 8px; font-size: 12px; }.coverage-summary strong { color: var(--color-text); }
.risk-budget-grid { padding: 0 20px 20px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.risk-budget-grid article { padding: 14px; display: grid; gap: 5px; background: var(--color-surface-subtle); border-radius: 9px; }
.risk-budget-grid article > span, .risk-budget-grid small { color: var(--color-text-soft); font-size: 12px; }
.risk-budget-grid strong { font-size: 20px; }
.risk-budget-unavailable { padding: 0 20px 20px; display: flex; flex-wrap: wrap; align-items: center; gap: 10px; color: var(--color-text-soft); font-size: 12px; }
.risk-hero { padding: 24px 26px; display: flex; align-items: center; justify-content: space-between; gap: 24px; color: #f7fbf9; background: #29473e; border-radius: 16px; box-shadow: var(--shadow-panel); }
.risk-hero--warning { background: #6b4b22; }
.risk-hero--danger { background: #6b3430; }
.risk-hero--pending { background: #4b5563; }
.risk-hero__eyebrow { display: block; margin-bottom: 7px; color: rgba(255,255,255,.68); font-size: 12px; font-weight: 700; letter-spacing: .12em; }
.risk-hero__title { margin: 0; font-size: 25px; line-height: 1.25; }
.risk-hero__description { margin: 8px 0 0; color: rgba(255,255,255,.75); font-size: 13px; }
.risk-hero__actions { display: flex; align-items: center; gap: 20px; }
.risk-hero__count { min-width: 82px; display: grid; text-align: right; }
.risk-hero__count strong { font-size: 27px; }
.risk-hero__count span { color: rgba(255,255,255,.7); font-size: 12px; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
.metric-card { min-width: 0; padding: 20px; display: grid; gap: 7px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; box-shadow: var(--shadow-panel); }
.metric-card__label { color: var(--color-text-soft); font-size: 13px; }
.metric-card__value { font-size: 25px; line-height: 1.15; }
.metric-card__meta { color: var(--color-text-muted); font-size: 12px; }
.section-hint { display: block; margin-top: 3px; color: var(--color-text-muted); font-size: 12px; }
.holdings-table-wrap { padding: 0 20px 16px; }
.holding-identity, .cell-stack { display: grid; gap: 3px; }
.holding-identity span, .cell-stack span { color: var(--color-text-muted); font-size: 12px; }
.cell-stack .tone-profit { color: var(--color-profit); }
.cell-stack .tone-loss { color: var(--color-loss); }
.risk-text--danger { color: var(--color-danger) !important; }
.risk-text--warning { color: var(--color-warning) !important; }
.risk-text--safe { color: var(--color-success) !important; }
.quote-tone--success { color: var(--color-success) !important; }
.quote-tone--warning { color: var(--color-warning) !important; }
.quote-tone--danger { color: var(--color-danger) !important; }
.mobile-holding-list { padding: 12px; }
.holding-card { width: 100%; padding: 15px; display: grid; gap: 14px; color: var(--color-text); text-align: left; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; }
.holding-card + .holding-card { margin-top: 10px; }
.holding-card__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.holding-card__header > span { display: grid; gap: 3px; }
.holding-card__header small, .holding-card__grid small { color: var(--color-text-muted); font-size: 11px; }
.holding-card__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.holding-card__grid > span { display: grid; gap: 4px; }
.holding-card__risk { padding-top: 10px; border-top: 1px solid var(--color-border); font-size: 12px; font-weight: 650; }
.today-alert { padding: 14px 17px; display: flex; align-items: center; justify-content: space-between; gap: 16px; color: var(--color-text-soft); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 10px; }
.today-alert > div { display: grid; gap: 4px; }
.today-alert strong { color: var(--color-text); font-size: 14px; }
.today-alert span { font-size: 12px; }
.today-alert--active { background: var(--color-warning-soft); border-color: #ecd7b5; }

@media (max-width: 1023px) { .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .metric-card--primary { grid-column: 1 / -1; } }
@media (max-width: 900px) { .holdings-table-wrap { display: none !important; } .mobile-holding-list { display: block; } }
@media (max-width: 767px) {
  .heading-actions .updated-at { display: none; }
  .risk-hero { padding: 19px; align-items: flex-start; flex-direction: column; }
  .risk-hero__title { font-size: 21px; }
  .risk-hero__actions { width: 100%; justify-content: space-between; }
  .risk-hero__count { text-align: left; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .metric-card { padding: 15px; }
  .metric-card--primary { grid-column: 1 / -1; }
  .metric-card__value { font-size: 20px; }
  .today-alert { align-items: flex-start; flex-direction: column; }
  .monitoring-trust { align-items: flex-start; flex-direction: column; }
  .coverage-summary { align-items: flex-start; flex-direction: column; }
  .risk-budget-grid { grid-template-columns: 1fr; }
}
</style>
