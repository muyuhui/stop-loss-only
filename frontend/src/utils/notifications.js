const PREFERENCES_KEY = 'notify-preferences'

export const PERMISSION_STATES = ['granted', 'denied', 'default', 'unsupported']

/**
 * 返回当前浏览器通知权限状态机：
 * 'granted' | 'denied' | 'default' | 'unsupported'
 * 每次发送前都必须重新校验，浏览器设置中的手动撤销要即时生效。
 */
export function permissionState() {
  const Notification = globalThis.Notification
  if (!Notification) return 'unsupported'
  if (Notification.permission === 'granted') return 'granted'
  if (Notification.permission === 'denied') return 'denied'
  return 'default'
}

/**
 * 显式请求通知权限。只在用户手势中调用（设置页开关），
 * 页面加载与轮询期间不得调用。返回最终权限状态。
 */
export async function ensurePermission() {
  const Notification = globalThis.Notification
  if (!Notification) return 'unsupported'
  if (Notification.permission === 'granted' || Notification.permission === 'denied') {
    return Notification.permission
  }
  try {
    return await Notification.requestPermission()
  } catch {
    return 'denied'
  }
}

export function getNotificationPreferences() {
  try {
    const stored = JSON.parse(globalThis.localStorage?.getItem(PREFERENCES_KEY) ?? 'null')
    return {
      notificationsEnabled: stored?.notificationsEnabled === true,
      soundEnabled: stored?.soundEnabled === true,
    }
  } catch {
    return { notificationsEnabled: false, soundEnabled: false }
  }
}

export function saveNotificationPreferences(preferences) {
  const next = {
    notificationsEnabled: preferences.notificationsEnabled === true,
    soundEnabled: preferences.soundEnabled === true,
  }
  try {
    globalThis.localStorage?.setItem(PREFERENCES_KEY, JSON.stringify(next))
  } catch {
    // 存储不可用时仅影响本次会话的偏好持久化
  }
  return next
}

/**
 * 发送一条浏览器系统通知，呈现站内告警快照。
 * 发送前校验 Notification.permission；环境不支持或发送异常时静默降级。
 */
export function sendTriggerNotification(alert, { onClick } = {}) {
  const Notification = globalThis.Notification
  if (!Notification || Notification.permission !== 'granted') return false
  const title = '止损触发'
  const body = `${alert.holding_name}(${alert.holding_code}) 当前价 ${alert.current_price} 触及止损价 ${alert.trigger_price}`
  try {
    const notification = new Notification(title, { body, tag: `trigger-${alert.id}` })
    notification.onclick = () => {
      if (onClick) {
        onClick(alert)
        return
      }
      globalThis.window?.focus?.()
      if (globalThis.location) globalThis.location.href = `/holdings/${alert.holding_id}`
    }
    return true
  } catch {
    return false
  }
}

/**
 * 发送一条明确标注为测试的浏览器通知，用于验证通知/声音管道。
 * 不创建告警、不调用 API、不写入任何业务事实；点击无副作用。
 * 发送前校验 Notification.permission；权限未授予时静默返回 false。
 */
export function sendTestNotification({ playSound = false } = {}) {
  const Notification = globalThis.Notification
  if (!Notification || Notification.permission !== 'granted') return false
  const title = '止损不止盈测试通知'
  const body = '测试持仓(000001) 当前价 9.80 触及止损价 9.00 —— 验证通知与提示音管道。'
  try {
    const notification = new Notification(title, { body, tag: 'test' })
    notification.onclick = () => {
      // 测试通知点击无副作用：不跳转、不标记已读、不改变业务状态
    }
    if (playSound) playTriggerChime()
    return true
  } catch {
    return false
  }
}

/**
 * 短促的双音提示，使用 Web Audio 振荡器，不打包音频资源。
 * 默认关闭，由设置页声音开关控制。失败时静默返回 false。
 */
export function playTriggerChime() {
  const AudioContextCtor = globalThis.AudioContext || globalThis.webkitAudioContext
  if (!AudioContextCtor) return false
  try {
    const context = new AudioContextCtor()
    const now = context.currentTime
    ;[880, 660].forEach((frequency, index) => {
      const oscillator = context.createOscillator()
      const gain = context.createGain()
      oscillator.type = 'sine'
      oscillator.frequency.value = frequency
      const start = now + index * 0.18
      gain.gain.setValueAtTime(0.0001, start)
      gain.gain.exponentialRampToValueAtTime(0.18, start + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.16)
      oscillator.connect(gain)
      gain.connect(context.destination)
      oscillator.start(start)
      oscillator.stop(start + 0.2)
    })
    return true
  } catch {
    return false
  }
}

/**
 * 告警触发通知器：维护加载基线（lastSeenAlertId）与已通知集合（notifiedAlertIds）。
 * - 首次成功响应只建立基线，不补发历史通知；
 * - 其后每次轮询返回比基线更新的告警时才调用 send 并记录去重；
 * - 同一条告警无论响应重复多少次只通知一次。
 */
export function createTriggerNotifier(send) {
  let established = false
  let lastSeenAlertId = 0
  const notifiedAlertIds = new Set()

  return function onAlertSnapshot(alerts) {
    const newest = alerts?.[0]
    if (!established) {
      established = true
      lastSeenAlertId = newest?.id ?? 0
      return null
    }
    if (!newest || newest.id <= lastSeenAlertId) return null
    if (notifiedAlertIds.has(newest.id)) return null
    lastSeenAlertId = newest.id
    notifiedAlertIds.add(newest.id)
    if (send) send(newest)
    return newest
  }
}
