const HIDDEN_MIN_INTERVAL_SECONDS = 60

export function createPoller(callback, timers = globalThis, documentRef = globalThis.document) {
  let timer = null
  let seconds = 0
  let wasVisible = true

  function isHidden() {
    return Boolean(documentRef && documentRef.visibilityState === 'hidden')
  }

  // 隐藏状态下降频为 max(60s, interval × 2)，仍执行回调；
  // 可见时恢复前台频率。浏览器对隐藏标签的计时节流（约 1/min）恰好与 60s 下限对齐。
  function effectiveIntervalSeconds() {
    return isHidden() ? Math.max(HIDDEN_MIN_INTERVAL_SECONDS, seconds * 2) : seconds
  }

  function schedule() {
    if (timer !== null) timers.clearInterval(timer)
    timer = timers.setInterval(callback, effectiveIntervalSeconds() * 1000)
  }

  // visibilitychange 转可见时立即触发一次刷新，不等下一个轮询周期。
  function handleVisibilityChange() {
    const visible = !isHidden()
    schedule()
    if (visible && !wasVisible) callback()
    wasVisible = visible
  }

  return {
    start(startSeconds) {
      seconds = startSeconds
      wasVisible = !isHidden()
      schedule()
      if (documentRef && typeof documentRef.addEventListener === 'function') {
        documentRef.addEventListener('visibilitychange', handleVisibilityChange)
      }
    },
    stop() {
      if (timer !== null) timers.clearInterval(timer)
      timer = null
      if (documentRef && typeof documentRef.removeEventListener === 'function') {
        documentRef.removeEventListener('visibilitychange', handleVisibilityChange)
      }
    },
    get active() {
      return timer !== null
    },
  }
}
