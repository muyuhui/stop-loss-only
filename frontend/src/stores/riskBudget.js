import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export const useRiskBudgetStore = defineStore('risk-budget', () => {
  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function fetchBudget() {
    loading.value = true
    error.value = null
    try {
      data.value = (await api.get('/risk/budget', {
        suppressErrorCodes: ['new_authority_required', 'feature_not_supported'],
      })).data
      return true
    } catch (cause) {
      data.value = null
      error.value = cause.response?.data?.detail?.error_code || 'risk_budget_unavailable'
      return false
    } finally {
      loading.value = false
    }
  }

  return { data, loading, error, fetchBudget }
})
