import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'

test('browser notification permission is requested only from the explicit action', () => {
  const source = fs.readFileSync(new URL('../src/views/Settings.vue', import.meta.url), 'utf8')
  assert.match(source, /Notification\.requestPermission\(\)/)
  assert.match(source, /@click="requestBrowserNotifications"/)
  assert.match(source, /notificationState !== 'default'/)
})
