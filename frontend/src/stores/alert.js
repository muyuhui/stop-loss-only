import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export const useAlertStore = defineStore('alert', () => {
  const unreadCount = ref(0)

  async function fetchUnreadCount() {
    try {
      const res = await api.get('/alerts/count')
      unreadCount.value = res.data.count
    } catch {
      // ignore polling errors
    }
  }

  return { unreadCount, fetchUnreadCount }
})
