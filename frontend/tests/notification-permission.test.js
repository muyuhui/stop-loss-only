import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'

test('stable settings do not expose browser notification permission', () => {
  const source = fs.readFileSync(new URL('../src/views/Settings.vue', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /Notification\.requestPermission\(\)/)
  assert.doesNotMatch(source, /requestBrowserNotifications/)
  assert.doesNotMatch(source, /Browser notifications/)
})
