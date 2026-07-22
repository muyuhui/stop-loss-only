import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export const useSettingsStore = defineStore('settings', () => {
  const pollInterval = ref(30)
  const monitorInterval = ref(5)

  async function fetchSettings() {
    try {
      const res = await api.get('/settings')
      pollInterval.value = res.data.poll_interval || 30
      monitorInterval.value = res.data.monitor_interval || 5
      return true
    } catch {
      return false
    }
  }

  async function saveSettings(data) {
    const res = await api.put('/settings', data)
    pollInterval.value = res.data.poll_interval
    monitorInterval.value = res.data.monitor_interval
  }

  return { pollInterval, monitorInterval, fetchSettings, saveSettings }
})
