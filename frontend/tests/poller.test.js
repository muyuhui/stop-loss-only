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
