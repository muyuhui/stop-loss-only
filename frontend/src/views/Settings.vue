<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { requestPriceRefresh } from '../api'
import DataState from '../components/DataState.vue'
import { useSettingsStore } from '../stores/settings'
import { useMonitoringStore } from '../stores/monitoring'
import { summarizeRefresh } from '../utils/refreshResult'
import { detectSettingsPreset, SETTINGS_PRESETS, settingsForPreset } from '../utils/settingsPresets'
import { useRequestState } from '../utils/requestState'

const settingsStore = useSettingsStore()
const monitoringStore = useMonitoringStore()
const pollInterval = ref(30)
const monitorInterval = ref(5)
const saving = ref(false)
const refreshing = ref(false)
const advancedOpen = ref(false)
const notificationState = ref(typeof Notification === 'undefined' ? 'unsupported' : Notification.permission)
const importPreview = ref(null)
const request = useRequestState()
const selectedPreset = computed(() => detectSettingsPreset(pollInterval.value, monitorInterval.value))

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
    advancedOpen.value = selectedPreset.value === 'custom'
    request.succeed()
  } catch {
    request.fail('设置加载失败，请重新尝试。')
  }
}

async function save() {
  if (saving.value) return
  const previous = { poll: settingsStore.pollInterval, monitor: settingsStore.monitorInterval }
  saving.value = true
  try {
    await settingsStore.saveSettings({ poll_interval: pollInterval.value, monitor_interval: monitorInterval.value })
    pollInterval.value = settingsStore.pollInterval
    monitorInterval.value = settingsStore.monitorInterval
    ElMessage.success('设置已保存并生效')
  } catch {
    pollInterval.value = previous.poll
    monitorInterval.value = previous.monitor
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
  } finally {
    refreshing.value = false
  }
}

async function requestBrowserNotifications() {
  if (typeof Notification === 'undefined') { notificationState.value = 'unsupported'; return }
  notificationState.value = await Notification.requestPermission()
}

async function previewImport(event) {
  const file = event.target.files?.[0]
  if (!file) return
  const content = await file.arrayBuffer()
  importPreview.value = (await api.post('/operations/import/preview', content, { headers: { 'Content-Type': 'application/octet-stream' } })).data
}
async function commitImport() { if (importPreview.value?.token) await api.post(`/operations/import/${importPreview.value.token}/commit`) }
async function createBackup() { await api.post('/operations/backup'); ElMessage.success('Backup created') }

onMounted(async () => { await loadSettings(); monitoringStore.refresh().catch(() => {}) })
</script>

<template>
  <section aria-labelledby="settings-title">
    <div class="page-heading"><div><h1 id="settings-title" class="page-title">设置</h1><p class="page-subtitle">选择适合你的刷新节奏，精确参数可随时展开</p></div></div>

    <DataState v-if="request.initialLoading.value" kind="loading" title="正在加载设置" />
    <DataState v-else-if="request.error.value && !request.hasData.value" kind="error" title="暂时无法加载设置" :description="request.error.value" action-label="重新加载" @action="loadSettings" />

    <div v-else class="settings-stack">
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
      <section class="manual-refresh" aria-label="Browser notifications">
        <div><h2>Browser notifications</h2><p v-if="notificationState === 'default'">Permission is requested only when you enable it; in-app alerts remain available.</p><p v-else-if="notificationState === 'granted'">Browser delivery is enabled and remains best-effort.</p><p v-else>Browser notifications are unavailable or denied; use in-app alerts.</p></div>
        <el-button plain :disabled="notificationState !== 'default'" @click="requestBrowserNotifications">Enable browser notifications</el-button>
      </section>
      <section class="manual-refresh" aria-label="Data portability">
        <div><h2>CSV import and export</h2><input type="file" accept=".csv,text/csv" @change="previewImport" /><p v-if="importPreview">{{ importPreview.valid }} valid rows; review errors before committing.</p></div>
        <div><el-button plain @click="commitImport" :disabled="!importPreview?.token">Commit import</el-button><a class="el-button el-button--default" href="/api/operations/export.csv">Export CSV</a></div>
      </section>
      <section class="manual-refresh" aria-label="Backup">
        <div><h2>Backup</h2><p>Creates a verified backup in the controlled local directory. Restore remains a stopped-service command.</p></div><el-button plain @click="createBackup">Create backup</el-button>
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
.advanced-settings label { display: grid; gap: 5px; }
.advanced-settings label > span:first-child { font-weight: 650; }
.advanced-settings small { color: var(--color-text-muted); font-size: 11px; }
.number-field { margin-top: 5px; display: flex; align-items: center; gap: 8px; }
.number-field em { color: var(--color-text-soft); font-size: 12px; font-style: normal; }
.settings-actions { display: flex; justify-content: flex-end; }
.manual-refresh { padding: 17px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; }
.manual-refresh h2 { margin: 0; font-size: 15px; }
.manual-refresh p { margin: 5px 0 0; color: var(--color-text-soft); font-size: 12px; }
@media (max-width: 767px) { .preset-grid, .advanced-settings { grid-template-columns: 1fr; } .preset-card { min-height: 110px; } .settings-actions .el-button { width: 100%; } .manual-refresh { align-items: stretch; flex-direction: column; } }
</style>
