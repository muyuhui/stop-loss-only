import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'

test('页面加载绝不请求通知权限；只有用户显式开启通知时才通过工具模块请求', () => {
  const source = fs.readFileSync(new URL('../src/views/Settings.vue', import.meta.url), 'utf8')
  // 设置页不得直接调用浏览器权限 API：请求只发生在 utils/notifications.js 的 ensurePermission（用户手势）中
  assert.doesNotMatch(source, /Notification\.requestPermission\(\)/)
  assert.doesNotMatch(source, /requestBrowserNotifications/)
  assert.doesNotMatch(source, /Browser notifications/)
  // 显式开启通知时通过工具模块请求权限
  assert.match(source, /ensurePermission/)
  assert.match(source, /utils\/notifications/)

  const moduleSource = fs.readFileSync(new URL('../src/utils/notifications.js', import.meta.url), 'utf8')
  assert.match(moduleSource, /requestPermission/)
  assert.match(moduleSource, /ensurePermission/)
})
