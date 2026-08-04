import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createTriggerNotifier,
  ensurePermission,
  getNotificationPreferences,
  permissionState,
  playTriggerChime,
  saveNotificationPreferences,
  sendTriggerNotification,
} from '../src/utils/notifications.js'


function FakeNotification(title, options) {
  this.title = title
  this.options = options
  this.onclick = null
  FakeNotification.created.push(this)
}

function mockNotification(permission, { requestResult } = {}) {
  const original = globalThis.Notification
  FakeNotification.created = []
  FakeNotification.permission = permission
  FakeNotification.requestPermission = async () => requestResult ?? permission
  globalThis.Notification = FakeNotification
  return { original, restore() { globalThis.Notification = original } }
}

function alertSnapshot(id, overrides = {}) {
  return { id, holding_name: '平安银行', holding_code: '000001', current_price: '9.80', trigger_price: '10.00', ...overrides }
}


test('加载基线不补发历史：首次响应只建立基线，其后新增才通知', () => {
  const sent = []
  const notifier = createTriggerNotifier((alert) => sent.push(alert))
  notifier([alertSnapshot(42)])
  assert.deepEqual(sent, [])
  const result = notifier([alertSnapshot(43)])
  assert.deepEqual(sent.map((alert) => alert.id), [43])
  assert.equal(result.id, 43)
})

test('同一条告警只通知一次：重复响应与旧 id 都不再触发', () => {
  const sent = []
  const notifier = createTriggerNotifier((alert) => sent.push(alert.id))
  notifier([alertSnapshot(42)])
  notifier([alertSnapshot(43)])
  notifier([alertSnapshot(43)])
  notifier([alertSnapshot(42)])
  notifier([alertSnapshot(44)])
  assert.deepEqual(sent, [43, 44])
})

test('空响应建立空基线：之后出现的告警视为新触发', () => {
  const sent = []
  const notifier = createTriggerNotifier((alert) => sent.push(alert.id))
  notifier([])
  notifier([alertSnapshot(1)])
  assert.deepEqual(sent, [1])
})

test('权限拒绝时静默跳过：不创建通知也不抛错', () => {
  const { restore } = mockNotification('denied')
  try {
    const result = sendTriggerNotification(alertSnapshot(1))
    assert.equal(result, false)
    assert.equal(FakeNotification.created.length, 0)
  } finally {
    restore()
  }
})

test('不支持环境：权限状态为 unsupported，请求权限同样返回 unsupported', async () => {
  const original = globalThis.Notification
  delete globalThis.Notification
  try {
    assert.equal(permissionState(), 'unsupported')
    assert.equal(await ensurePermission(), 'unsupported')
  } finally {
    globalThis.Notification = original
  }
})

test('权限已授予时创建通知，内容使用告警快照并携带处置跳转', () => {
  const { restore } = mockNotification('granted')
  try {
    const result = sendTriggerNotification(alertSnapshot(7))
    assert.equal(result, true)
    assert.equal(FakeNotification.created.length, 1)
    const { title, options, onclick } = FakeNotification.created[0]
    assert.equal(title, '止损触发')
    assert.match(options.body, /平安银行\(000001\)/)
    assert.match(options.body, /当前价 9\.80/)
    assert.match(options.body, /止损价 10\.00/)
    assert.equal(typeof onclick, 'function')
  } finally {
    restore()
  }
})

test('点击通知跳转到对应持仓详情', () => {
  const { restore } = mockNotification('granted')
  const href = { value: '' }
  globalThis.location = { href: href.value }
  globalThis.window = { focus() {} }
  try {
    sendTriggerNotification(alertSnapshot(7, { holding_id: 99 }))
    FakeNotification.created[0].onclick()
    assert.equal(globalThis.location.href, '/holdings/99')
  } finally {
    restore()
    delete globalThis.location
    delete globalThis.window
  }
})

test('发送异常不抛出：构造器抛错时静默返回 false', () => {
  const original = globalThis.Notification
  globalThis.Notification = function Boom() { throw new Error('send failed') }
  globalThis.Notification.permission = 'granted'
  try {
    assert.equal(sendTriggerNotification(alertSnapshot(1)), false)
  } finally {
    globalThis.Notification = original
  }
})

test('偏好持久化默认全关，保存后可读回', () => {
  const originalStorage = globalThis.localStorage
  const store = new Map()
  globalThis.localStorage = {
    getItem(key) { return store.has(key) ? store.get(key) : null },
    setItem(key, value) { store.set(key, String(value)) },
  }
  try {
    assert.deepEqual(getNotificationPreferences(), { notificationsEnabled: false, soundEnabled: false })
    const saved = saveNotificationPreferences({ notificationsEnabled: true, soundEnabled: false })
    assert.deepEqual(saved, { notificationsEnabled: true, soundEnabled: false })
    assert.deepEqual(getNotificationPreferences(), { notificationsEnabled: true, soundEnabled: false })
  } finally {
    globalThis.localStorage = originalStorage
  }
})

test('提示音默认依赖环境：无 AudioContext 时静默返回 false', () => {
  const original = globalThis.AudioContext
  delete globalThis.AudioContext
  try {
    assert.equal(playTriggerChime(), false)
  } finally {
    globalThis.AudioContext = original
  }
})
