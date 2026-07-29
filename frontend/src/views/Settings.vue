<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { refreshErrorMessage, requestPriceRefresh } from '../api'
import DataState from '../components/DataState.vue'
import { useSettingsStore } from '../stores/settings'
import { useMonitoringStore } from '../stores/monitoring'
import { useRuntimeCapabilitiesStore } from '../stores/runtimeCapabilities'
import { summarizeRefresh } from '../utils/refreshResult'
import { detectSettingsPreset, SETTINGS_PRESETS, settingsForPreset } from '../utils/settingsPresets'
import { useRequestState } from '../utils/requestState'

const settingsStore = useSettingsStore()
const monitoringStore = useMonitoringStore()
const runtimeCapabilities = useRuntimeCapabilitiesStore()
const pollInterval = ref(30)
const monitorInterval = ref(5)
const portfolioEquity = ref(null)
const portfolioRiskLimitPct = ref(5)
const defaultPositionRiskLimitPct = ref(1)
const saving = ref(false)
const refreshing = ref(false)
const advancedOpen = ref(false)
const request = useRequestState()
const selectedPreset = computed(() => detectSettingsPreset(pollInterval.value, monitorInterval.value))
const riskSettingsAvailable = computed(() => (
  runtimeCapabilities.isAvailable('risk_budget_reads')
  || runtimeCapabilities.isAvailable('risk_plan_previews')
))

function selectPreset(id) {
  const values = settingsForPreset(id)
  if (!values) return
  pollInterval.value = values.pollInterval
  monitorInterval.value = values.monitorInterval
}

async function loadSettings() {
  request.begin()
  try {
    const loaded = await settingsStore.fetchSettings()
    if (!loaded) throw new Error('settings unavailable')
    pollInterval.value = settingsStore.pollInterval
    monitorInterval.value = settingsStore.monitorInterval
    portfolioEquity.value = settingsStore.portfolioEquity == null ? null : Number(settingsStore.portfolioEquity)
    portfolioRiskLimitPct.value = Number(settingsStore.portfolioRiskLimitPct)
    defaultPositionRiskLimitPct.value = Number(settingsStore.defaultPositionRiskLimitPct)
    advancedOpen.value = selectedPreset.value === 'custom'
    request.succeed()
  } catch {
    request.fail('设置加载失败，请重新尝试。')
  }
}

async function save() {
  if (saving.value) return
  const previous = {
    poll: settingsStore.pollInterval, monitor: settingsStore.monitorInterval,
    equity: settingsStore.portfolioEquity, portfolioPct: settingsStore.portfolioRiskLimitPct,
    positionPct: settingsStore.defaultPositionRiskLimitPct,
  }
  saving.value = true
  try {
    const payload = {
      poll_interval: pollInterval.value,
      monitor_interval: monitorInterval.value,
    }
    if (riskSettingsAvailable.value) Object.assign(payload, {
      portfolio_equity: portfolioEquity.value,
      portfolio_risk_limit_pct: portfolioRiskLimitPct.value,
      default_position_risk_limit_pct: defaultPositionRiskLimitPct.value,
    })
    await settingsStore.saveSettings(payload)
    pollInterval.value = settingsStore.pollInterval
    monitorInterval.value = settingsStore.monitorInterval
    portfolioEquity.value = settingsStore.portfolioEquity == null ? null : Number(settingsStore.portfolioEquity)
    portfolioRiskLimitPct.value = Number(settingsStore.portfolioRiskLimitPct)
    defaultPositionRiskLimitPct.value = Number(settingsStore.defaultPositionRiskLimitPct)
    ElMessage.success('设置已保存并生效')
  } catch {
    pollInterval.value = previous.poll
    monitorInterval.value = previous.monitor
    portfolioEquity.value = previous.equity === null ? null : Number(previous.equity)
    portfolioRiskLimitPct.value = Number(previous.portfolioPct)
    defaultPositionRiskLimitPct.value = Number(previous.positionPct)
    ElMessage.error('设置保存失败，已恢复原值。')
  } finally {
    saving.value = false
  }
}

async function refreshPrices() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    const res = await requestPriceRefresh()
    const summary = summarizeRefresh(res.data)
    ElMessage[summary.type](summary.message)
  } catch (error) {
    ElMessage.error(refreshErrorMessage(error))
  } finally {
    refreshing.value = false
  }
}

async function createBackup() { await api.post('/operations/backup'); ElMessage.success('备份已创建并校验') }

onMounted(async () => { await loadSettings(); monitoringStore.refresh().catch(() => {}) })
</script>

<template>
  <section aria-labelledby="settings-title">
    <div class="page-heading"><div><h1 id="settings-title" class="page-title">设置</h1><p class="page-subtitle">选择适合你的刷新节奏，精确参数可随时展开</p></div></div>

    <DataState v-if="request.initialLoading.value" kind="loading" title="正在加载设置" />
    <DataState v-else-if="request.error.value && !request.hasData.value" kind="error" title="暂时无法加载设置" :description="request.error.value" action-label="重新加载" @action="loadSettings" />

    <div v-else class="settings-stack">
      <section v-if="riskSettingsAvailable" class="panel" aria-labelledby="risk-policy-title">
        <header class="panel__header"><div><h2 id="risk-policy-title" class="panel__title">风险预算</h2><span class="panel-hint">账户权益由你手工维护，不代表券商实时余额</span></div></header>
        <div class="panel__body settings-body">
          <div class="risk-settings-grid">
            <label><span>组合权益</span><small>用于把百分比风险换算为金额；发生入金、出金或较大变化后请更新。</small><span class="number-field"><el-input-number v-model="portfolioEquity" :min="0.01" :precision="2" :controls="false" aria-label="手工维护的组合权益" /><em>元</em></span></label>
            <label><span>组合风险上限</span><small>所有开放仓位触及止损时的预计总损失上限。</small><span class="number-field"><el-input-number v-model="portfolioRiskLimitPct" :min="0.01" :max="100" :precision="2" :controls="false" aria-label="组合风险上限百分比" /><em>%</em></span></label>
            <label><span>默认单笔风险上限</span><small>规划新仓位时默认使用，可在单次规划中调低或调整。</small><span class="number-field"><el-input-number v-model="defaultPositionRiskLimitPct" :min="0.01" :max="portfolioRiskLimitPct || 100" :precision="2" :controls="false" aria-label="默认单笔风险上限百分比" /><em>%</em></span></label>
          </div>
          <p class="manual-equity-note">手工权益最近更新：{{ settingsStore.portfolioEquityUpdatedAt ? new Date(settingsStore.portfolioEquityUpdatedAt).toLocaleString('zh-CN', { hour12: false }) : '尚未设置' }}</p>
          <div class="settings-actions"><el-button type="primary" :loading="saving" @click="save">保存风险与运行设置</el-button></div>
        </div>
      </section>

      <section class="panel" aria-labelledby="frequency-title">
        <header class="panel__header"><div><h2 id="frequency-title" class="panel__title">刷新频率</h2><span class="panel-hint">当前：{{ selectedPreset === 'custom' ? '自定义' : SETTINGS_PRESETS.find(item => item.id === selectedPreset)?.label }}</span></div></header>
        <div class="panel__body settings-body">
          <div class="preset-grid" role="radiogroup" aria-label="刷新频率预设">
            <button v-for="preset in SETTINGS_PRESETS" :key="preset.id" type="button" role="radio" :aria-checked="selectedPreset === preset.id" class="preset-card" :class="{ 'is-active': selectedPreset === preset.id }" @click="selectPreset(preset.id)">
              <span class="preset-card__radio" aria-hidden="true"></span>
              <strong>{{ preset.label }}</strong>
              <small>{{ preset.description }}</small>
              <span class="preset-card__meta">页面 {{ preset.pollInterval }} 秒 · 监控 {{ preset.monitorInterval }} 分钟</span>
            </button>
          </div>

          <button class="advanced-toggle" type="button" :aria-expanded="advancedOpen" aria-controls="advanced-settings" @click="advancedOpen = !advancedOpen">
            <span>{{ advancedOpen ? '收起高级设置' : '展开高级设置' }}</span><span aria-hidden="true">{{ advancedOpen ? '−' : '+' }}</span>
          </button>

          <div v-if="advancedOpen" id="advanced-settings" class="advanced-settings">
            <label><span>页面轮询间隔</span><small>仪表盘和告警前端刷新频率</small><span class="number-field"><el-input-number v-model="pollInterval" :min="5" :max="300" :controls="false" aria-label="页面轮询间隔（秒）" /><em>秒</em></span></label>
            <label><span>价格监控间隔</span><small>后端拉取行情并检查止损的频率</small><span class="number-field"><el-input-number v-model="monitorInterval" :min="1" :max="60" :controls="false" aria-label="价格监控间隔（分钟）" /><em>分钟</em></span></label>
          </div>

          <div class="settings-actions"><el-button type="primary" :loading="saving" @click="save">保存并应用</el-button></div>
        </div>
      </section>

      <section class="manual-refresh" aria-labelledby="manual-refresh-title">
        <div><h2 id="manual-refresh-title">手动刷新行情</h2><p>立即拉取所有活动持仓价格并检查止损。通常无需频繁使用。</p></div>
        <el-button plain :loading="refreshing" @click="refreshPrices">立即刷新</el-button>
      </section>
      <section class="manual-refresh" aria-label="运行时诊断">
        <div><h2>运行时诊断</h2><p>页面轮询：{{ pollInterval }} 秒；后端监控：{{ monitorInterval }} 分钟；调度器：{{ monitoringStore.data?.scheduler_running ? '运行中' : '未运行或未知' }}。</p></div>
        <el-button plain :loading="monitoringStore.loading" @click="monitoringStore.refresh().catch(() => {})">刷新状态</el-button>
      </section>
      <section class="manual-refresh" aria-label="数据库备份">
        <div><h2>数据库备份</h2><p>在受控本地目录创建并校验备份；恢复操作需要先停止服务。</p></div><el-button plain @click="createBackup">创建备份</el-button>
      </section>
    </div>
  </section>
</template>

<style scoped>
.settings-stack { display: grid; gap: 16px; }
.panel__header > div { display: grid; gap: 3px; }
.panel-hint { color: var(--color-text-muted); font-size: 11px; }
.settings-body { display: grid; gap: 18px; }
.preset-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.preset-card { position: relative; min-height: 132px; padding: 18px; display: grid; align-content: start; gap: 7px; color: var(--color-text); text-align: left; background: var(--color-surface-subtle); border: 1px solid var(--color-border); border-radius: 12px; cursor: pointer; }
.preset-card:hover { border-color: #b7c9c2; }
.preset-card.is-active { background: var(--color-brand-soft); border-color: var(--color-brand); box-shadow: inset 0 0 0 1px var(--color-brand); }
.preset-card__radio { position: absolute; top: 15px; right: 15px; width: 16px; height: 16px; background: #fff; border: 1px solid #b6bcb5; border-radius: 50%; }
.preset-card.is-active .preset-card__radio { border: 5px solid var(--color-brand); }
.preset-card strong { font-size: 17px; }
.preset-card small { color: var(--color-text-soft); font-size: 12px; }
.preset-card__meta { margin-top: 4px; color: var(--color-text-muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.advanced-toggle { width: 100%; padding: 13px 15px; display: flex; align-items: center; justify-content: space-between; color: var(--color-text); background: var(--color-surface-subtle); border: 1px solid var(--color-border); border-radius: 9px; cursor: pointer; font-weight: 650; }
.advanced-settings { padding: 17px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; background: var(--color-surface-subtle); border-radius: 10px; }
.advanced-settings label, .risk-settings-grid label { display: grid; gap: 5px; }
.advanced-settings label > span:first-child, .risk-settings-grid label > span:first-child { font-weight: 650; }
.advanced-settings small, .risk-settings-grid small { color: var(--color-text-muted); font-size: 11px; }
.risk-settings-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; }
.risk-settings-grid :deep(.el-input-number) { width: 100%; }
.manual-equity-note { margin: 0; color: var(--color-text-soft); font-size: 12px; }
.number-field { margin-top: 5px; display: flex; align-items: center; gap: 8px; }
.number-field em { color: var(--color-text-soft); font-size: 12px; font-style: normal; }
.settings-actions { display: flex; justify-content: flex-end; }
.manual-refresh { padding: 17px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; }
.manual-refresh h2 { margin: 0; font-size: 15px; }
.manual-refresh p { margin: 5px 0 0; color: var(--color-text-soft); font-size: 12px; }
@media (max-width: 767px) { .preset-grid, .advanced-settings, .risk-settings-grid { grid-template-columns: 1fr; } .preset-card { min-height: 110px; } .settings-actions .el-button { width: 100%; } .manual-refresh { align-items: stretch; flex-direction: column; } }
</style>
