import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export const useSettingsStore = defineStore('settings', () => {
  const pollInterval = ref(30)
  const monitorInterval = ref(5)
  const portfolioEquity = ref(null)
  const portfolioRiskLimitPct = ref('5')
  const defaultPositionRiskLimitPct = ref('1')
  const portfolioEquityUpdatedAt = ref(null)
  const deepseekApiKeyConfigured = ref(false)
  const desktopNotificationsEnabled = ref(false)
  const desktopNotificationMode = ref('full')
  const desktopNotificationsPaused = ref(false)

  function apply(data) {
    pollInterval.value = data.poll_interval || 30
    monitorInterval.value = data.monitor_interval || 5
    portfolioEquity.value = data.portfolio_equity
    portfolioRiskLimitPct.value = data.portfolio_risk_limit_pct ?? '5'
    defaultPositionRiskLimitPct.value = data.default_position_risk_limit_pct ?? '1'
    portfolioEquityUpdatedAt.value = data.portfolio_equity_updated_at
    deepseekApiKeyConfigured.value = data.deepseek_api_key_configured === true
    desktopNotificationsEnabled.value = data.desktop_notifications_enabled === true
    desktopNotificationMode.value = data.desktop_notification_mode === 'redacted' ? 'redacted' : 'full'
    desktopNotificationsPaused.value = data.desktop_notifications_paused === true
  }

  async function fetchSettings() {
    try {
      const res = await api.get('/settings')
      apply(res.data)
      return true
    } catch {
      return false
    }
  }

  async function saveSettings(data) {
    const res = await api.put('/settings', data)
    apply(res.data)
    return res.data
  }

  return {
    pollInterval, monitorInterval, portfolioEquity, portfolioRiskLimitPct,
    defaultPositionRiskLimitPct, portfolioEquityUpdatedAt, deepseekApiKeyConfigured,
    desktopNotificationsEnabled, desktopNotificationMode, desktopNotificationsPaused,
    fetchSettings, saveSettings,
  }
})
