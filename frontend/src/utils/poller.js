export function createPoller(callback, timers = globalThis) {
  let timer = null
  return {
    start(seconds) {
      if (timer !== null) timers.clearInterval(timer)
      timer = timers.setInterval(callback, seconds * 1000)
    },
    stop() {
      if (timer !== null) timers.clearInterval(timer)
      timer = null
    },
    get active() {
      return timer !== null
    },
  }
}
