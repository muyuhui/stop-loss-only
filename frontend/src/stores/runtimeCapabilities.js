import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import api from '../api'

export const CLOSED_CAPABILITIES = Object.freeze({
  legacy_holding_writes: false,
  shadow_diagnostics: false,
  risk_budget_reads: false,
  risk_plan_previews: false,
  risk_covered_position_creation: false,
  position_lifecycle_writes: false,
  csv_portability: false,
  webhook_delivery: false,
})

export const useRuntimeCapabilitiesStore = defineStore('runtime-capabilities', () => {
  const authorityStage = ref('unknown')
  const stableRuntimeSupported = ref(false)
  const capabilities = ref({ ...CLOSED_CAPABILITIES })
  const status = ref('idle')
  const error = ref(null)

  const loaded = computed(() => status.value === 'ready' || status.value === 'error')

  function isAvailable(name) {
    return capabilities.value[name] === true
  }

  function apply(payload) {
    authorityStage.value = payload.authority_stage
    stableRuntimeSupported.value = payload.stable_runtime_supported === true
    capabilities.value = { ...CLOSED_CAPABILITIES, ...(payload.capabilities || {}) }
    status.value = 'ready'
    error.value = null
  }

  async function fetchCapabilities() {
    status.value = 'loading'
    error.value = null
    try {
      apply((await api.get('/runtime/capabilities', { suppressGlobalError: true })).data)
      return true
    } catch {
      authorityStage.value = 'unknown'
      stableRuntimeSupported.value = false
      capabilities.value = { ...CLOSED_CAPABILITIES }
      status.value = 'error'
      error.value = '无法确认可选功能状态；核心持仓功能仍可继续使用。'
      return false
    }
  }

  return {
    authorityStage,
    stableRuntimeSupported,
    capabilities,
    status,
    error,
    loaded,
    isAvailable,
    apply,
    fetchCapabilities,
  }
})
