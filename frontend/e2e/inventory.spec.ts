import { expect, test, type Page } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'

async function prepare(page: Page): Promise<number> {
  await page.goto('/inventory')
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
  const session = (await (await page.request.get('/api/auth/session')).json()) as {
    csrf_token: string
  }
  const response = await page.request.post('/api/shops', {
    headers: { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token },
    data: {
      code: `stock-${test.info().testId.slice(-16)}`,
      name: '合成库存店铺',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'Asia/Shanghai',
    },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return ((await response.json()) as { id: number }).id
}

async function importStock(page: Page, shop: number, age = 1): Promise<void> {
  await page.goto('/imports')
  await page.getByLabel('所属店铺').selectOption(String(shop))
  await page.getByLabel('数据身份').selectOption('synthetic')
  await page.getByLabel('报表类型').selectOption('inventory')
  const stamp = new Date(Date.now() - age * 3600000).toISOString()
  await page.getByLabel('CSV / Excel 文件').setInputFiles({
    name: 'stock.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(`sku,available,snapshot_at,safety_threshold\n001,3,${stamp},5\n`),
  })
  await page.getByRole('button', { name: '上传并查看映射' }).click()
  await page.getByRole('button', { name: '校验并预览' }).click()
  await page.getByRole('button', { name: '确认导入', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('批次已导入')
}

async function inventory(page: Page, shop: number): Promise<void> {
  await page.goto('/inventory')
  await page.getByLabel('所属店铺').selectOption(String(shop))
  await page.getByLabel('数据身份').selectOption('synthetic')
  await expect(page).toHaveURL(/\/inventory$/)
  await expect(page.getByRole('heading', { name: '库存判断，从快照出发。' })).toBeVisible()
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
}

test('inventory import, source, refresh, revoke and missing data', async ({ page }) => {
  const shop = await prepare(page)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await inventory(page, shop)
  await expect(page.getByRole('heading', { name: '库存未知 / 未检查' })).toBeVisible()
  await importStock(page, shop)
  await inventory(page, shop)
  await expect(page.getByText('低于安全阈值', { exact: true })).toBeVisible()
  await page.getByText(/来源：stock.csv/).click()
  await page.getByRole('button', { name: '查看来源原始行' }).click()
  await expect(page.getByRole('region', { name: '来源原始值' })).toContainText('available')
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-inventory-desktop.png'),
    fullPage: true,
  })
  await page.reload()
  await page.getByLabel('所属店铺').selectOption(String(shop))
  await page.getByLabel('数据身份').selectOption('synthetic')
  await expect(page.getByText('快照可售 3', { exact: true })).toBeVisible()
  await page.goto('/imports')
  await page.getByLabel('所属店铺').selectOption(String(shop))
  await expect(page.getByRole('button', { name: /查看批次/ })).toHaveCount(1)
  await page.getByRole('button', { name: /查看批次/ }).click()
  await page.getByRole('button', { name: '撤销此批次' }).click()
  await page.getByRole('button', { name: '确认撤销' }).click()
  await expect(page.getByText('已撤销', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '清除源数据' }).click()
  await page.getByRole('button', { name: '确认清除' }).click()
  await expect(page.getByText('已清除', { exact: true })).toBeVisible()
  await inventory(page, shop)
  await expect(page.getByRole('heading', { name: '库存未知 / 未检查' })).toBeVisible()
  expect(errors).toEqual([])
})

test('mobile inventory expiration and user chosen freshness window', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const shop = await prepare(page)
  await importStock(page, shop, 30)
  await inventory(page, shop)
  await expect(page.getByText('当前库存未知', { exact: true })).toBeVisible()
  await expect(page.getByText('快照可售 3', { exact: true })).toBeVisible()
  await page.getByLabel('快照有效时长（小时）').fill('48')
  await page.getByRole('button', { name: '刷新库存' }).click()
  await expect(page.getByText('低于安全阈值', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-inventory-mobile.png'),
    fullPage: true,
  })
})
