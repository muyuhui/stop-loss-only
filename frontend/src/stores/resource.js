import { ref } from 'vue'

// Keeps the last successful response visible during background failures and
// coalesces callers that request the same resource at the same time.
export function createResource(loader) {
  const data = ref(null)
  const error = ref(null)
  const loading = ref(false)
  const updatedAt = ref(null)
  let inFlight = null

  async function refresh() {
    if (inFlight) return inFlight
    loading.value = data.value === null
    inFlight = loader().then((value) => {
      data.value = value; error.value = null; updatedAt.value = Date.now()
      return value
    }).catch((cause) => {
      error.value = cause; throw cause
    }).finally(() => { loading.value = false; inFlight = null })
    return inFlight
  }
  return { data, error, loading, updatedAt, refresh }
}
