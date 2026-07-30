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
