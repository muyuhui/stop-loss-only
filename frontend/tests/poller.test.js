import test from 'node:test'
import assert from 'node:assert/strict'

import { createPoller } from '../src/utils/poller.js'


function fakeTimers() {
  let next = 1
  const active = new Map()
  return {
    active,
    setInterval(callback, delay) {
      const id = next++
      active.set(id, { callback, delay })
      return id
    },
    clearInterval(id) {
      active.delete(id)
    },
  }
}


function fakeDocument() {
  const listeners = new Map()
  return {
    listeners,
    visibilityState: 'visible',
    addEventListener(type, fn) {
      listeners.set(type, fn)
    },
    removeEventListener(type, fn) {
      if (listeners.get(type) === fn) listeners.delete(type)
    },
    fire(type) {
      listeners.get(type)?.()
    },
  }
}


test('restarting a poller replaces the previous timer', () => {
  const timers = fakeTimers()
  const poller = createPoller(() => {}, timers)
  poller.start(30)
  poller.start(45)
  assert.equal(timers.active.size, 1)
  assert.equal([...timers.active.values()][0].delay, 45000)
})


test('stopping a poller clears its timer', () => {
  const timers = fakeTimers()
  const poller = createPoller(() => {}, timers)
  poller.start(30)
  poller.stop()
  assert.equal(timers.active.size, 0)
  assert.equal(poller.active, false)
})


test('hidden 状态下轮询降频为 max(60, interval×2) 且回调仍执行', () => {
  const timers = fakeTimers()
  const documentRef = fakeDocument()
  documentRef.visibilityState = 'hidden'
  let calls = 0
  const poller = createPoller(() => { calls += 1 }, timers, documentRef)
  poller.start(10)
  assert.equal([...timers.active.values()][0].delay, 60000)
  ;[...timers.active.values()][0].callback()
  assert.equal(calls, 1)
  poller.stop()
})


test('可见状态使用前台频率', () => {
  const timers = fakeTimers()
  const poller = createPoller(() => {}, timers, fakeDocument())
  poller.start(10)
  assert.equal([...timers.active.values()][0].delay, 10000)
  poller.stop()
})


test('隐藏频率不高于前台频率：任意配置下降频值都大于等于前台值', () => {
  for (const interval of [5, 10, 30, 45, 120, 300]) {
    const timers = fakeTimers()
    const documentRef = fakeDocument()
    documentRef.visibilityState = 'hidden'
    const poller = createPoller(() => {}, timers, documentRef)
    poller.start(interval)
    const hiddenDelay = [...timers.active.values()][0].delay
    assert.ok(hiddenDelay >= interval * 1000)
    assert.equal(hiddenDelay, Math.max(60, interval * 2) * 1000)
    poller.stop()
  }
})


test('从隐藏恢复可见：立即触发一次回调并恢复前台频率', () => {
  const timers = fakeTimers()
  const documentRef = fakeDocument()
  documentRef.visibilityState = 'hidden'
  let calls = 0
  const poller = createPoller(() => { calls += 1 }, timers, documentRef)
  poller.start(30)
  assert.equal([...timers.active.values()][0].delay, 60000)

  documentRef.visibilityState = 'visible'
  documentRef.fire('visibilitychange')
  assert.equal(calls, 1)
  assert.equal([...timers.active.values()][0].delay, 30000)

  documentRef.fire('visibilitychange')
  assert.equal(calls, 1)
  poller.stop()
})


test('停止时移除 visibilitychange 监听', () => {
  const timers = fakeTimers()
  const documentRef = fakeDocument()
  let calls = 0
  const poller = createPoller(() => { calls += 1 }, timers, documentRef)
  poller.start(30)
  poller.stop()
  assert.equal(documentRef.listeners.size, 0)
  assert.equal(calls, 0)
})
