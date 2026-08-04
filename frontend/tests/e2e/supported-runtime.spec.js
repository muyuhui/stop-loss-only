import { expect, test } from '@playwright/test'

async function assertPageIntegrity(page, browserErrors) {
  await expect(page.locator('body')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
  const clippedCommands = await page.locator('button:visible, a:visible').evaluateAll((items) => items
    .filter((item) => !item.querySelector('.el-badge, .mobile-nav__badge') && item.scrollWidth > item.clientWidth + 1)
    .map((item) => item.textContent?.trim()).filter(Boolean))
  expect(clippedCommands).toEqual([])
  expect(browserErrors).toEqual([])
}

async function clickVisibleNav(page, label) {
  await page.locator('a:visible').filter({ hasText: label }).first().click()
}

async function installNotificationStub(page, granted) {
  await page.addInitScript((permission) => {
    window.__notifications = { created: [] }
    class FakeNotification {
      constructor(title, options) {
        this.title = title
        this.options = options
        window.__notifications.created.push({ title, options })
      }
    }
    FakeNotification.permission = permission
    window.Notification = FakeNotification
  }, granted ? 'granted' : 'denied')
}

async function forceVisibility(page, visible) {
  await page.evaluate((isVisible) => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => (isVisible ? 'visible' : 'hidden') })
    document.dispatchEvent(new Event('visibilitychange'))
  }, visible)
}

async function createTriggeredAlert(page, testInfo) {
  const name = `通知验证-${testInfo.project.name}`
  const created = await page.request.post('/api/holdings', { data: {
    code: '000009', name, type: 'stock', buy_price: 10, quantity: 100,
    buy_date: '2026-07-24', stop_loss_method: 'fixed', stop_loss_value: 9,
  } })
  expect(created.ok()).toBe(true)
  const refresh = await page.request.post('/api/prices/refresh')
  expect(refresh.ok()).toBe(true)
  await expect.poll(async () => {
    const alerts = await page.request.get('/api/alerts?unread=true&size=1')
    return (await alerts.json()).items?.length ?? 0
  }, { timeout: 15_000 }).toBeGreaterThan(0)
  return { name }
}

function trackBrowserErrors(page, browserErrors) {
  page.on('pageerror', (error) => browserErrors.push(`pageerror: ${error.message}`))
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(`console: ${message.text()}`)
  })
}

test('legacy 风险试算、刷新触发、告警查看与手动平仓', async ({ page }, testInfo) => {
  const browserErrors = []
  const previewRequests = []
  const businessWritesDuringPlanning = []
  let planningPhase = false
  page.on('pageerror', (error) => browserErrors.push(`pageerror: ${error.message}`))
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(`console: ${message.text()}`)
  })
  page.on('request', (request) => {
    const url = request.url()
    if (/\/api\/risk\/plans\/(?:preview|add-on-preview)$/.test(url)) {
      previewRequests.push(`${request.method()} ${url}`)
    }
    if (
      planningPhase
      && request.method() !== 'GET'
      && /\/api\/(?:holdings|positions)(?:\/|$)/.test(url)
    ) {
      businessWritesDuringPlanning.push(`${request.method()} ${url}`)
    }
  })

  const holdingName = `浏览器验证-${testInfo.project.name}`
  await page.goto('/planner')
  await expect(page.getByRole('heading', { name: '风险试算' })).toBeVisible()
  await expect(page.locator('a[href="/planner"]:visible')).toHaveCount(1)
  await expect(page.getByRole('tab', { name: '新仓试算' })).toBeVisible()
  expect(previewRequests).toEqual([])

  await page.goto('/holdings')
  await page.getByRole('button', { name: '新增持仓' }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByPlaceholder('例如 000001').fill('000001')
  await dialog.getByPlaceholder('例如 平安银行').fill(holdingName)
  const numbers = dialog.locator('.el-input-number input')
  await numbers.nth(0).fill('10')
  await numbers.nth(1).fill('100')
  await dialog.getByPlaceholder('选择日期').fill('2026-07-24')
  await numbers.nth(2).fill('10')
  const createResponsePromise = page.waitForResponse((response) => (
    response.url().endsWith('/api/holdings') && response.request().method() === 'POST'
  ))
  await dialog.getByRole('button', { name: '保存持仓' }).click()
  const holdingId = (await (await createResponsePromise).json()).id
  await expect(page.locator('strong:visible').filter({ hasText: holdingName }).first()).toBeVisible()
  const unpricedCard = page.locator('.position-card').filter({ hasText: holdingName })
  await expect(unpricedCard).toContainText('未定价')
  await expect(unpricedCard).toContainText('风险未知')
  await expect(unpricedCard).not.toContainText('0.00%')
  await assertPageIntegrity(page, browserErrors)

  await clickVisibleNav(page, '设置')
  await expect(page.getByRole('heading', { name: '设置' })).toBeVisible()
  await expect(page.getByText('风险预算', { exact: true })).toBeVisible()
  await page.getByLabel('手工维护的组合权益').fill('100000')
  await Promise.all([
    page.waitForResponse((response) => response.url().endsWith('/api/settings') && response.request().method() === 'PUT'),
    page.getByRole('button', { name: '保存风险与运行设置' }).click(),
  ])

  planningPhase = true
  await clickVisibleNav(page, '试算')
  await page.getByLabel('计划标的代码').fill('000002')
  await page.getByLabel('计划标的名称').fill('新仓试算标的')
  await page.getByLabel('计划买入价').fill('20')
  await page.getByLabel('止损参数').fill('10')
  await page.getByLabel('预计买入费用').fill('5')
  await page.getByLabel('预计退出费用').fill('5')
  await Promise.all([
    page.waitForResponse((response) => response.url().endsWith('/api/risk/plans/preview')),
    page.getByRole('button', { name: '计算风险上限' }).click(),
  ])
  await expect(page.getByText('风险约束下的最大数量', { exact: true })).toBeVisible()
  await expect(page.getByText('400 股', { exact: true })).toBeVisible()
  await expect(page.getByText('这是上限而不是买满建议；可以选择更小数量。', { exact: true })).toBeVisible()
  await expect(page.locator('body')).not.toContainText(/推荐标的|自动下单|确认创建仓位|记录加仓/)
  await assertPageIntegrity(page, browserErrors)

  await page.goto(`/holdings/${holdingId}`)
  await expect(page.getByRole('heading', { name: holdingName })).toBeVisible()
  await page.getByRole('button', { name: '加仓风险试算' }).click()
  await expect(page).toHaveURL(new RegExp(`/planner\\?mode=add-on&holding_id=${holdingId}`))
  await expect(page.getByRole('tab', { name: '加仓试算' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByText('保留止损价')).toBeVisible()
  await expect(page.getByLabel('计划加仓成交价')).toHaveValue('')
  await page.getByLabel('计划加仓成交价').fill('10')
  await page.getByLabel('加仓预计买入费用').fill('5')
  await page.getByLabel('加仓预计退出费用').fill('5')
  await Promise.all([
    page.waitForResponse((response) => response.url().endsWith('/api/risk/plans/add-on-preview')),
    page.getByRole('button', { name: '计算风险上限' }).click(),
  ])
  await expect(page.getByText('800 股')).toBeVisible()
  await expect(page.getByText('当前持仓风险')).toBeVisible()
  await expect(page.getByText('试算后持仓风险')).toBeVisible()
  await expect(page.getByText('试算后组合风险')).toBeVisible()
  await expect(page.locator('body')).not.toContainText(/推荐标的|自动下单|确认创建仓位|记录加仓/)
  expect(previewRequests).toHaveLength(2)
  expect(businessWritesDuringPlanning).toEqual([])
  await assertPageIntegrity(page, browserErrors)
  planningPhase = false

  await page.goto('/')
  const dashboardHolding = page.locator('.holding-card').filter({ hasText: holdingName })
  await expect(dashboardHolding).toContainText('未定价')
  await expect(dashboardHolding).toContainText('风险未知')
  await expect(dashboardHolding).not.toContainText('0.00%')
  await expect(page.getByText('风险预算', { exact: true })).toBeVisible()
  await expect(page.locator('a[href="/planner"]:visible')).toHaveCount(1)
  await assertPageIntegrity(page, browserErrors)

  await clickVisibleNav(page, '设置')
  await expect(page.locator('body')).not.toContainText(/CSV|Webhook|Browser notifications|retention/i)
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/prices/refresh')),
    page.getByRole('button', { name: '立即刷新' }).click(),
  ])
  await assertPageIntegrity(page, browserErrors)

  await clickVisibleNav(page, '告警')
  await expect(page.getByLabel('搜索告警')).toBeVisible()
  await expect(page.getByRole('combobox', { name: '阅读状态' })).toBeVisible()
  await expect(page.getByRole('combobox', { name: '处置状态' })).toBeVisible()
  await expect(page.locator('body')).not.toContainText(/全部生命周期|风险优先|最新优先|Lifecycle|Risk|Sort/)
  await page.getByLabel('搜索告警').fill(holdingName)
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/alerts?') && response.url().includes('search=')),
    page.getByRole('button', { name: '搜索', exact: true }).click(),
  ])
  await expect(page).toHaveURL(/search=/)
  const alert = page.locator('.alert-card').filter({ hasText: holdingName })
  await expect(alert).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('搜索告警')).toHaveValue(holdingName)
  await expect(alert).toBeVisible()
  await assertPageIntegrity(page, browserErrors)
  await alert.getByRole('button', { name: '查看持仓' }).click()
  await expect(page).toHaveURL(/\/holdings\/\d+$/)
  await expect(page.getByRole('heading', { name: holdingName })).toBeVisible()

  const closeButton = page.getByRole('button', { name: '确认平仓', exact: true }).first()
  if (testInfo.project.name === 'mobile-390') {
    await closeButton.scrollIntoViewIfNeeded()
    const buttonBox = await closeButton.boundingBox()
    const navBox = await page.locator('.mobile-nav').boundingBox()
    expect(buttonBox && navBox && buttonBox.y + buttonBox.height <= navBox.y + 1).toBe(true)
  }
  await page.getByLabel('平仓价格').fill('8.7')
  await closeButton.click()
  await page.getByRole('button', { name: '确认平仓', exact: true }).last().click()
  await expect(page.getByText('已关闭').first()).toBeVisible()
  await expect(page.locator('.el-message--error')).toHaveCount(0)
  await assertPageIntegrity(page, browserErrors)
})

test('DeepSeek 设置、成功复盘、受限加仓入口与失败重试', async ({ page }, testInfo) => {
  const browserErrors = []
  page.on('pageerror', (error) => browserErrors.push(`pageerror: ${error.message}`))
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(`console: ${message.text()}`)
  })

  await page.route('**/api/runtime/capabilities', async (route) => {
    const response = await route.fetch()
    const payload = await response.json()
    payload.capabilities.risk_plan_previews = false
    await route.fulfill({ response, json: payload })
  })

  await page.request.put('/api/settings', { data: {
    clear_deepseek_api_key: true,
    portfolio_equity: 100000,
    portfolio_risk_limit_pct: 5,
    default_position_risk_limit_pct: 1,
  } })
  const holdingName = `AI复盘-${testInfo.project.name}`
  const created = await page.request.post('/api/holdings', { data: {
    code: '000003', name: holdingName, type: 'stock', buy_price: 10, quantity: 100,
    buy_date: '2026-07-24', stop_loss_method: 'fixed', stop_loss_value: 8,
  } })
  expect(created.ok()).toBe(true)
  const holdingId = (await created.json()).id

  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: 'DeepSeek 持仓复盘' })).toBeVisible()
  await expect(page.getByText('未配置', { exact: true })).toBeVisible()
  await expect(page.getByText(/目标持仓的近期行情、止损数据和聚合风险事实会发送给 DeepSeek/)).toBeVisible()
  const successKey = 'fixture-ai-add-on-key'
  await page.getByLabel('DeepSeek API Key').fill(successKey)
  const saveResponsePromise = page.waitForResponse((response) => (
    response.url().endsWith('/api/settings') && response.request().method() === 'PUT'
  ))
  await page.getByRole('button', { name: '保存 DeepSeek Key' }).click()
  const savePayload = await (await saveResponsePromise).text()
  expect(savePayload).not.toContain(successKey)
  await expect(page.getByText('已配置', { exact: true })).toBeVisible()
  await Promise.all([
    page.waitForResponse((response) => response.url().endsWith('/api/ai/deepseek/test')),
    page.getByRole('button', { name: '检测连接' }).click(),
  ])
  await expect(page.getByText(/连接成功：fixture-deepseek/)).toBeVisible()
  await assertPageIntegrity(page, browserErrors)

  await page.goto(`/holdings/${holdingId}`)
  await expect(page.getByRole('heading', { name: holdingName })).toBeVisible()
  await Promise.all([
    page.waitForResponse((response) => response.url().endsWith(`/api/ai/holdings/${holdingId}/review`)),
    page.getByRole('button', { name: '更新行情并 AI 复盘' }).click(),
  ])
  await expect(page.getByText('近期行情与止损风险已完成复盘。')).toBeVisible()
  await expect(page.getByText('可进一步试算加仓风险', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '主要依据' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '风险情景' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '数据局限' })).toBeVisible()
  await expect(page.getByText(/可信程度：中/)).toBeVisible()
  await expect(page.getByText(/历史截至/)).toBeVisible()
  await expect(page.getByText(/DeepSeek · fixture-deepseek/)).toBeVisible()
  await expect(page.getByRole('button', { name: '进入加仓风险试算' })).toHaveCount(0)
  await expect(page.getByText(/复盘不是收益预测或交易指令/)).toBeVisible()
  await assertPageIntegrity(page, browserErrors)

  const failedKey = 'fixture-ai-timeout-key'
  const failedSetting = await page.request.put('/api/settings', {
    data: { deepseek_api_key: failedKey },
  })
  expect(failedSetting.ok()).toBe(true)
  expect(await failedSetting.text()).not.toContain(failedKey)
  const failedReview = page.waitForResponse((response) => (
    response.url().endsWith(`/api/ai/holdings/${holdingId}/review`)
    && response.status() === 504
  ))
  await page.getByRole('button', { name: '重新复盘' }).last().click()
  await failedReview
  await expect(page.getByText(/DeepSeek 响应超时/)).toBeVisible()
  await expect(page.getByRole('button', { name: '修改止损' })).toBeVisible()
  await expect(page.getByText('手动平仓', { exact: true })).toBeVisible()
  expect(browserErrors).toEqual([
    expect.stringContaining('server responded with a status of 504'),
  ])
  browserErrors.length = 0
  await assertPageIntegrity(page, browserErrors)

  await page.request.put('/api/settings', { data: { deepseek_api_key: successKey } })
  await Promise.all([
    page.waitForResponse((response) => (
      response.url().endsWith(`/api/ai/holdings/${holdingId}/review`) && response.ok()
    )),
    page.getByRole('button', { name: '重新复盘' }).click(),
  ])
  await expect(page.getByText('近期行情与止损风险已完成复盘。')).toBeVisible()
  await assertPageIntegrity(page, browserErrors)
})

test('通知权限已授予时，新触发止损创建浏览器通知', async ({ page }, testInfo) => {
  const browserErrors = []
  trackBrowserErrors(page, browserErrors)
  await installNotificationStub(page, true)

  // 用户显式开启系统通知（页面加载绝不主动请求）；
  // el-switch 的可访问名位于隐藏 input 上，点击可见的 .el-switch 根节点
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: '设置' })).toBeVisible()
  const notificationSwitch = page.locator('.el-switch').first()
  await notificationSwitch.click()
  await expect(notificationSwitch).toHaveClass(/is-checked/)
  await expect(page.getByText('已授予', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => window.Notification.permission)).toBe('granted')

  const baseline = page.waitForResponse((response) => (
    response.url().includes('/api/alerts?') && response.url().includes('unread=')
  ))
  await page.goto('/')
  await baseline
  await createTriggeredAlert(page, testInfo)

  // 隐藏 → 恢复可见：立即刷新告警，不等下一个轮询周期
  await forceVisibility(page, false)
  await forceVisibility(page, true)

  await expect.poll(async () => (
    page.evaluate(() => window.__notifications.created.length)
  ), { timeout: 10_000 }).toBe(1)
  const record = await page.evaluate(() => window.__notifications.created[0])
  expect(record.title).toBe('止损触发')
  expect(record.options.body).toContain(testInfo.project.name)
  expect(record.options.body).toContain('000009')
  expect(record.options.body).toContain('8.8')
  expect(record.options.body).toContain('止损价 9')
  await assertPageIntegrity(page, browserErrors)
})

test('通知权限被拒绝时不创建浏览器通知且未读徽标仍在', async ({ page }, testInfo) => {
  const browserErrors = []
  trackBrowserErrors(page, browserErrors)
  await installNotificationStub(page, false)

  const baseline = page.waitForResponse((response) => (
    response.url().includes('/api/alerts?') && response.url().includes('unread=')
  ))
  await page.goto('/')
  await baseline
  await createTriggeredAlert(page, testInfo)

  await forceVisibility(page, false)
  await forceVisibility(page, true)

  await expect.poll(async () => Number(await page.locator('.el-badge__content').textContent())).toBeGreaterThan(0)
  await page.waitForTimeout(500)
  expect(await page.evaluate(() => window.__notifications.created.length)).toBe(0)
  await assertPageIntegrity(page, browserErrors)
})

test('测试通知在权限已授予时创建样本通知且不产生业务写入', async ({ page }) => {
  const browserErrors = []
  trackBrowserErrors(page, browserErrors)
  await installNotificationStub(page, true)
  const businessWrites = []
  page.on('request', (request) => {
    if (request.method() !== 'GET' && request.url().includes('/api/')) {
      businessWrites.push(`${request.method()} ${request.url()}`)
    }
  })

  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: '设置' })).toBeVisible()
  await page.getByRole('button', { name: '发送测试通知', exact: true }).click()

  await expect.poll(async () => (
    page.evaluate(() => window.__notifications.created.length)
  ), { timeout: 10_000 }).toBe(1)
  const record = await page.evaluate(() => window.__notifications.created[0])
  expect(record.title).toContain('测试')
  expect(record.options.tag).toBe('test')
  expect(businessWrites).toEqual([])
  await assertPageIntegrity(page, browserErrors)
})

test('测试通知在权限拒绝时禁用且显示重新授权指引', async ({ page }) => {
  const browserErrors = []
  trackBrowserErrors(page, browserErrors)
  await installNotificationStub(page, false)

  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: '设置' })).toBeVisible()
  await expect(page.getByRole('button', { name: '发送测试通知', exact: true })).toBeDisabled()
  await expect(page.getByText('浏览器站点设置')).toBeVisible()
  expect(await page.evaluate(() => window.__notifications.created.length)).toBe(0)
  await assertPageIntegrity(page, browserErrors)
})
