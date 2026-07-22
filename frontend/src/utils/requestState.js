import { computed, ref } from 'vue'

export function useRequestState(options = {}) {
  const now = options.now || (() => Date.now())
  const hasData = ref(false)
  const loading = ref(false)
  const refreshing = ref(false)
  const error = ref('')
  const lastUpdatedAt = ref(null)

  const initialLoading = computed(() => loading.value && !hasData.value)

  function begin() {
    error.value = ''
    if (hasData.value) refreshing.value = true
    else loading.value = true
  }

  function succeed() {
    hasData.value = true
    loading.value = false
    refreshing.value = false
    error.value = ''
    lastUpdatedAt.value = now()
  }

  function fail(reason = '暂时无法获取最新数据') {
    loading.value = false
    refreshing.value = false
    error.value = reason
  }

  function isStale(intervalSeconds, at = now()) {
    if (!lastUpdatedAt.value || !intervalSeconds) return false
    return at - lastUpdatedAt.value > intervalSeconds * 2000
  }

  return { hasData, loading, refreshing, error, lastUpdatedAt, initialLoading, begin, succeed, fail, isStale }
}
