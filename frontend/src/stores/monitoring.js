import { defineStore } from 'pinia'
import api from '../api'
import { createResource } from './resource'

export const useMonitoringStore = defineStore('monitoring', () => {
  const status = createResource(() => api.get('/monitoring/status').then(r => r.data))
  return { ...status }
})
