import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export const useAlertStore = defineStore('alert', () => {
  const unreadCount = ref(0)
  const countLoaded = ref(false)

  async function fetchUnreadCount() {
    try {
      const res = await api.get('/alerts/count')
      unreadCount.value = res.data.count
      countLoaded.value = true
    } catch {
      // ignore polling errors
    }
  }

  return { unreadCount, countLoaded, fetchUnreadCount }
})
