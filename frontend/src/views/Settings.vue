<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { refreshErrorMessage, requestPriceRefresh } from '../api'
import DataState from '../components/DataState.vue'
import { useSettingsStore } from '../stores/settings'
import { useMonitoringStore } from '../stores/monitoring'
import { useRuntimeCapabilitiesStore } from '../stores/runtimeCapabilities'
import { summarizeRefresh } from '../utils/refreshResult'
import { detectSettingsPreset, SETTINGS_PRESETS, settingsForPreset } from '../utils/settingsPresets'
import { useRequestState } from '../utils/requestState'
import {
  ensurePermission,
  getNotificationPreferences,
  permissionState,
  saveNotificationPreferences,
  sendTestNotification,
} from '../utils/notifications'

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
const deepseekApiKey = ref('')
const savingDeepseek = ref(false)
const testingDeepseek = ref(false)
const request = useRequestState()
const selectedPreset = computed(() => detectSettingsPreset(pollInterval.value, monitorInterval.value))
const riskSettingsAvailable = computed(() => (
  runtimeCapabilities.isAvailable('risk_budget_reads')
  || runtimeCapabilities.isAvailable('risk_plan_previews')
))
const aiReviewAvailable = computed(() => runtimeCapabilities.isAvailable('ai_holding_reviews'))
const notificationsAvailable = computed(() => runtimeCapabilities.isAvailable('browser_notifications'))
const desktopNotificationsAvailable = computed(() => runtimeCapabilities.isAvailable('desktop_notifications'))
const notificationPrefs = ref(getNotificationPreferences())
const permission = ref(permissionState())
const permissionRequesting = ref(false)
const desktopEnabled = ref(false)
const desktopMode = ref('full')
const desktopPaused = ref(false)
const desktopSaving = ref(false)
const permissionLabels = { granted: '已授予', denied: '被拒绝', default: '未授权', unsupported: '不支持' }
const permissionLabel = computed(() => permissionLabels[permission.value] || permission.value)
const permissionTagType = computed(() => ({
  granted: 'success', denied: 'danger', default: 'info', unsupported: 'info',
}[permission.value] || 'info'))

// 通知开关：只在用户手势中请求权限（页面加载绝不主动请求）；被拒或未授予时开关保持关闭
async function toggleNotifications(enabled) {
  if (!enabled) {
    notificationPrefs.value = saveNotificationPreferences({ ...notificationPrefs.value, notificationsEnabled: false })
    return
  }
  permissionRequesting.value = true
  try {
    permission.value = await ensurePermission()
    if (permission.value === 'granted') {
      notificationPrefs.value = saveNotificationPreferences({ ...notificationPrefs.value, notificationsEnabled: true })
    } else {
      notificationPrefs.value = saveNotificationPreferences({ ...notificationPrefs.value, notificationsEnabled: false })
    }
  } finally {
    permissionRequesting.value = false
  }
}

function toggleSound(enabled) {
  notificationPrefs.value = saveNotificationPreferences({ ...notificationPrefs.value, soundEnabled: enabled })
}

// 测试通知：仅权限已授予时发送；声音开关开启时同步播放提示音；不产生任何业务事实
function sendTest() {
  if (permission.value !== 'granted') return
  sendTestNotification({ playSound: notificationPrefs.value.soundEnabled })
}

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
    desktopEnabled.value = settingsStore.desktopNotificationsEnabled
    desktopMode.value = settingsStore.desktopNotificationMode
    desktopPaused.value = settingsStore.desktopNotificationsPaused
    advancedOpen.value = selectedPreset.value === 'custom'
    request.succeed()
  } catch {
    request.fail('设置加载失败，请重新尝试。')
  }
}

async function saveDesktopSettings() {
  if (desktopSaving.value) return
  desktopSaving.value = true
  try {
    await settingsStore.saveSettings({
      desktop_notifications_enabled: desktopEnabled.value,
      desktop_notification_mode: desktopMode.value,
      desktop_notifications_paused: desktopPaused.value,
    })
    ElMessage.success('桌面通知设置已保存')
  } catch {
    desktopEnabled.value = settingsStore.desktopNotificationsEnabled
    desktopMode.value = settingsStore.desktopNotificationMode
    desktopPaused.value = settingsStore.desktopNotificationsPaused
    ElMessage.error('桌面通知设置保存失败，已恢复原值。')
  } finally {
    desktopSaving.value = false
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

async function saveDeepseekKey() {
  const value = deepseekApiKey.value.trim()
  if (savingDeepseek.value || value.length < 16) {
    if (value.length < 16) ElMessage.warning('请输入有效的 DeepSeek API Key')
    return
  }
  savingDeepseek.value = true
  try {
    await settingsStore.saveSettings({ deepseek_api_key: value })
    deepseekApiKey.value = ''
    ElMessage.success('DeepSeek Key 已加密保存在本机')
  } catch {
    ElMessage.error('DeepSeek Key 保存失败，原配置保持不变。')
  } finally {
    savingDeepseek.value = false
  }
}

async function clearDeepseekKey() {
  try {
    await ElMessageBox.confirm('清除后将无法生成新的 AI 持仓复盘。', '清除 DeepSeek Key', {
      confirmButtonText: '确认清除', cancelButtonText: '取消', type: 'warning',
    })
  } catch { return }
  savingDeepseek.value = true
  try {
    await settingsStore.saveSettings({ clear_deepseek_api_key: true })
    deepseekApiKey.value = ''
    ElMessage.success('DeepSeek Key 已清除')
  } catch {
    ElMessage.error('清除失败，原配置保持不变。')
  } finally {
    savingDeepseek.value = false
  }
}

async function testDeepseekConnection() {
  if (testingDeepseek.value) return
  testingDeepseek.value = true
  try {
    const response = await api.post('/ai/deepseek/test', undefined, {
      timeout: 60000,
      suppressErrorCodes: ['ai_not_configured', 'ai_timeout', 'ai_rate_limited', 'ai_unavailable', 'ai_response_invalid'],
    })
    ElMessage.success(`连接成功：${response.data.model}`)
  } catch (error) {
    const code = error?.response?.data?.detail?.error_code
    const message = {
      ai_not_configured: '请先保存 DeepSeek API Key。',
      ai_timeout: 'DeepSeek 响应超时，请稍后重试。',
      ai_rate_limited: '请求过于频繁，请稍后重试。',
      ai_response_invalid: 'DeepSeek 返回内容无法验证。',
    }[code] || 'DeepSeek 暂时不可用，请检查 Key 或稍后重试。'
    ElMessage.error(message)
  } finally {
    testingDeepseek.value = false
  }
}

async function createBackup() { await api.post('/operations/backup'); ElMessage.success('备份已创建并校验') }

onMounted(async () => {
  await loadSettings()
  monitoringStore.refresh().catch(() => {})
  // 以浏览器实际权限状态修正显示与持久化偏好（用户可能在浏览器设置中手动撤销）
  permission.value = permissionState()
  if (notificationPrefs.value.notificationsEnabled && permission.value !== 'granted') {
    notificationPrefs.value = saveNotificationPreferences({ ...notificationPrefs.value, notificationsEnabled: false })
  }
})
</script>

<template>
  <section aria-labelledby="settings-title">
    <div class="page-heading"><div><h1 id="settings-title" class="page-title">设置</h1><p class="page-subtitle">选择适合你的刷新节奏，精确参数可随时展开</p></div></div>

    <DataState v-if="request.initialLoading.value" kind="loading" title="正在加载设置" />
    <DataState v-else-if="request.error.value && !request.hasData.value" kind="error" title="暂时无法加载设置" :description="request.error.value" action-label="重新加载" @action="loadSettings" />

    <div v-else class="settings-stack">
      <section v-if="aiReviewAvailable" class="panel" aria-labelledby="deepseek-settings-title">
        <header class="panel__header">
          <div><h2 id="deepseek-settings-title" class="panel__title">DeepSeek 持仓复盘</h2><span class="panel-hint">第一版固定使用 DeepSeek，不会自动交易</span></div>
          <el-tag :type="settingsStore.deepseekApiKeyConfigured ? 'success' : 'info'">{{ settingsStore.deepseekApiKeyConfigured ? '已配置' : '未配置' }}</el-tag>
        </header>
        <div class="panel__body settings-body">
          <p class="ai-disclosure">生成复盘时，目标持仓的近期行情、止损数据和聚合风险事实会发送给 DeepSeek。API Key 仅加密保存在当前 Windows 用户的本机，不进入数据库、日志或备份。</p>
          <label class="deepseek-key-field">
            <span>{{ settingsStore.deepseekApiKeyConfigured ? '替换 API Key' : 'API Key' }}</span>
            <small>保存后不会再次显示原文；连接检测不会发送任何持仓数据。</small>
            <el-input v-model="deepseekApiKey" type="password" show-password autocomplete="off" aria-label="DeepSeek API Key" placeholder="输入 DeepSeek API Key" />
          </label>
          <div class="settings-actions ai-settings-actions">
            <el-button v-if="settingsStore.deepseekApiKeyConfigured" :loading="testingDeepseek" @click="testDeepseekConnection">检测连接</el-button>
            <el-button v-if="settingsStore.deepseekApiKeyConfigured" type="danger" plain :loading="savingDeepseek" @click="clearDeepseekKey">清除 Key</el-button>
            <el-button type="primary" :loading="savingDeepseek" @click="saveDeepseekKey">保存 DeepSeek Key</el-button>
          </div>
        </div>
      </section>

      <section v-if="notificationsAvailable" class="panel" aria-labelledby="notifications-settings-title">
        <header class="panel__header">
          <div><h2 id="notifications-settings-title" class="panel__title">触发通知</h2><span class="panel-hint">新触发止损时通过浏览器系统通知与提示音提醒你</span></div>
          <el-tag :type="permissionTagType" size="small">{{ permissionLabel }}</el-tag>
        </header>
        <div class="panel__body settings-body">
          <div class="notification-options">
            <label class="notification-option">
              <span>系统通知</span>
              <small>开启时将在本次点击中请求通知权限；页面加载不会主动请求。</small>
              <el-switch :model-value="notificationPrefs.notificationsEnabled" :loading="permissionRequesting" aria-label="系统通知开关" @change="toggleNotifications" />
            </label>
            <label class="notification-option">
              <span>提示音</span>
              <small>新触发时播放短促提示音（默认关闭），与系统通知独立控制。</small>
              <el-switch :model-value="notificationPrefs.soundEnabled" aria-label="提示音开关" @change="toggleSound" />
            </label>
          </div>
          <div class="notification-test">
            <div><strong>发送测试通知</strong><small>立即验证浏览器通知与提示音管道，不产生告警。</small></div>
            <el-button :disabled="permission !== 'granted'" @click="sendTest">发送测试通知</el-button>
          </div>
          <div v-if="desktopNotificationsAvailable" class="desktop-notification-options">
            <div class="desktop-notification-heading"><strong>桌面通知（本地）</strong><small>浏览器关闭时仍能收到触发提醒，仅本机显示</small></div>
            <label class="notification-option">
              <span>启用桌面通知</span>
              <small>由后端直接发送 Windows 通知，不依赖浏览器标签页是否打开。</small>
              <el-switch v-model="desktopEnabled" aria-label="桌面通知开关" :loading="desktopSaving" @change="saveDesktopSettings" />
            </label>
            <label class="notification-option">
              <span>通知内容</span>
              <small>脱敏模式不出现任何持仓名称、代码或价格，适合演示或共享屏幕。</small>
              <el-radio-group v-model="desktopMode" aria-label="桌面通知内容模式" @change="saveDesktopSettings">
                <el-radio-button value="full">完整</el-radio-button>
                <el-radio-button value="redacted">脱敏</el-radio-button>
              </el-radio-group>
            </label>
            <label class="notification-option">
              <span>演示模式</span>
              <small>完全暂停所有桌面通知；演示或共享屏幕时打开。</small>
              <el-switch v-model="desktopPaused" aria-label="演示模式开关" :loading="desktopSaving" @change="saveDesktopSettings" />
            </label>
          </div>
          <p v-if="permission === 'denied'" class="permission-guidance">通知权限已被浏览器拒绝。请在浏览器站点设置中为本站点重新授权通知后，再打开开关重试；未读徽标与提示音不受影响。</p>
          <p v-else-if="permission === 'unsupported'" class="permission-guidance">当前浏览器不支持系统通知；未读徽标仍会在标签标题与告警铃铛上显示。</p>
          <p v-else-if="permission === 'default'" class="permission-guidance">请先开启系统通知开关完成授权，再发送测试通知。</p>
        </div>
      </section>

      <section v-if="riskSettingsAvailable" class="panel" aria-labelledby="risk-policy-title">
        <header class="panel__header"><div><h2 id="risk-policy-title" class="panel__title">风险预算</h2><span class="panel-hint">账户权益由你手工维护，不代表券商实时余额</span></div></header>
        <div class="panel__body settings-body">
          <div class="risk-settings-grid">
            <label><span>组合权益</span><small>用于把百分比风险换算为金额；发生入金、出金或较大变化后请更新。</small><span class="number-field"><el-input-number v-model="portfolioEquity" :min="0.01" :precision="2" :controls="false" aria-label="手工维护的组合权益" /><em>元</em></span></label>
            <label><span>组合风险上限</span><small>所有开放仓位触及止损时的预计总损失上限。</small><span class="number-field"><el-input-number v-model="portfolioRiskLimitPct" :min="0.01" :max="100" :precision="2" :controls="false" aria-label="组合风险上限百分比" /><em>%</em></span></label>
            <label><span>默认单笔风险上限</span><small>新仓和加仓风险试算默认使用，可在单次试算中调整。</small><span class="number-field"><el-input-number v-model="defaultPositionRiskLimitPct" :min="0.01" :max="portfolioRiskLimitPct || 100" :precision="2" :controls="false" aria-label="默认单笔风险上限百分比" /><em>%</em></span></label>
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
.ai-disclosure { margin: 0; color: var(--color-text-soft); font-size: 12px; line-height: 1.7; }
.notification-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.notification-option { display: grid; gap: 5px; align-content: start; }
.notification-option > span { font-weight: 650; }
.notification-option small { color: var(--color-text-muted); font-size: 11px; }
.notification-option .el-switch { justify-self: start; }
.permission-guidance { margin: 0; color: var(--color-text-soft); font-size: 12px; line-height: 1.7; }
.notification-test { padding: 13px 15px; display: flex; align-items: center; justify-content: space-between; gap: 12px; background: var(--color-surface-subtle); border: 1px solid var(--color-border); border-radius: 9px; }
.notification-test div { display: grid; gap: 3px; }
.notification-test strong { font-size: 13px; }
.notification-test small { color: var(--color-text-muted); font-size: 11px; }
.desktop-notification-options { margin-top: 16px; padding-top: 14px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; border-top: 1px dashed var(--color-border); }
.desktop-notification-heading { grid-column: 1 / -1; display: grid; gap: 3px; }
.desktop-notification-heading small { color: var(--color-text-muted); font-size: 11px; }
.deepseek-key-field { display: grid; gap: 6px; }
.deepseek-key-field > span { font-weight: 650; }
.deepseek-key-field small { color: var(--color-text-muted); font-size: 11px; }
.ai-settings-actions { gap: 8px; flex-wrap: wrap; }
.manual-refresh { padding: 17px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; }
.manual-refresh h2 { margin: 0; font-size: 15px; }
.manual-refresh p { margin: 5px 0 0; color: var(--color-text-soft); font-size: 12px; }
@media (max-width: 767px) { .preset-grid, .advanced-settings, .risk-settings-grid, .notification-options { grid-template-columns: 1fr; } .preset-card { min-height: 110px; } .settings-actions .el-button { width: 100%; } .ai-settings-actions { flex-direction: column-reverse; } .manual-refresh { align-items: stretch; flex-direction: column; } }
</style>
