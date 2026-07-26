import { expect, test } from '@playwright/test'

async function assertPageIntegrity(page, browserErrors) {
  await expect(page.locator('body')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
  const clippedCommands = await page.locator('button:visible, a:visible').evaluateAll((items) => items
    .filter((item) => item.scrollWidth > item.clientWidth + 1)
    .map((item) => item.textContent?.trim()).filter(Boolean))
  expect(clippedCommands).toEqual([])
  expect(browserErrors).toEqual([])
}

async function clickVisibleNav(page, label) {
  await page.locator('a:visible').filter({ hasText: label }).first().click()
}

test('legacy 创建、刷新触发、告警查看与手动平仓', async ({ page }, testInfo) => {
  const browserErrors = []
  page.on('pageerror', (error) => browserErrors.push(`pageerror: ${error.message}`))
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(`console: ${message.text()}`)
  })

  const holdingName = `浏览器验证-${testInfo.project.name}`
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
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/holdings') && response.request().method() === 'POST'),
    dialog.getByRole('button', { name: '保存持仓' }).click(),
  ])
  await expect(page.locator('strong:visible').filter({ hasText: holdingName }).first()).toBeVisible()
  await assertPageIntegrity(page, browserErrors)

  await clickVisibleNav(page, '设置')
  await expect(page.getByRole('heading', { name: '设置' })).toBeVisible()
  await expect(page.locator('body')).not.toContainText(/CSV|Webhook|Browser notifications|retention/i)
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/prices/refresh')),
    page.getByRole('button', { name: '立即刷新' }).click(),
  ])
  await assertPageIntegrity(page, browserErrors)

  await clickVisibleNav(page, '告警')
  const alert = page.locator('.alert-card').filter({ hasText: holdingName })
  await expect(alert).toBeVisible()
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
  await assertPageIntegrity(page, browserErrors)
})
