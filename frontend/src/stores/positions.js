import { defineStore } from 'pinia'
import api from '../api'
import { createResource } from './resource'

export const usePositionsStore = defineStore('positions', () => {
  const list = createResource(() => api.get('/positions').then(r => r.data))
  return { ...list }
})
