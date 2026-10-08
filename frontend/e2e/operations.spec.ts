import { expect, test, type Page } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'

async function setup(page: Page): Promise<{ shop: number; headers: Record<string, string> }> {
  await page.goto('/')
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
  const session = (await (await page.request.get('/api/auth/session')).json()) as {
    csrf_token: string
  }
  const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
  const response = await page.request.post('/api/shops', {
    headers,
    data: {
      code: `ops-${test.info().testId.slice(-16)}`,
      name: '合成运营店铺',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'Asia/Shanghai',
    },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  const shop = ((await response.json()) as { id: number }).id
  await page.reload()
  await page.getByLabel('所属店铺').selectOption(String(shop))
  await page.getByLabel('数据身份').selectOption('synthetic')
  return { shop, headers }
}

async function importInventory(
  page: Page,
  shop: number,
  headers: Record<string, string>,
): Promise<number> {
  const query = new URLSearchParams({
    filename: 'ops-stock.csv',
    kind: 'inventory',
    data_identity: 'synthetic',
    source_channel: 'generic',
    timezone: 'UTC',
  })
  const stamp = new Date(Date.now() - 3600000).toISOString()
  const uploaded = await page.request.post(`/api/shops/${shop}/imports?${query}`, {
    headers: { ...headers, 'Content-Type': 'text/csv' },
    data: `sku,available,snapshot_at,safety_threshold\nOPS-001,2,${stamp},5\n`,
  })
  expect(uploaded.ok(), await uploaded.text()).toBeTruthy()
  const batch = (await uploaded.json()) as {
    id: number
    version: number
    mapping: Record<string, string>
  }
  const previewed = await page.request.post(`/api/imports/${batch.id}/preview`, {
    headers,
    data: { version: batch.version, mapping: batch.mapping },
  })
  expect(previewed.ok(), await previewed.text()).toBeTruthy()
  const preview = (await previewed.json()) as { version: number }
  const committed = await page.request.post(`/api/imports/${batch.id}/commit`, {
    headers,
    data: { version: preview.version },
  })
  expect(committed.ok(), await committed.text()).toBeTruthy()
  return batch.id
}

test('operations source, approval, defer, completion, replay and source clearing', async ({
  page,
}) => {
  const { shop, headers } = await setup(page)
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  const batch = await importInventory(page, shop, headers)
  await page.getByRole('button', { name: '运行今日运营' }).click()
  const result = page.getByRole('region', { name: '巡检结果' })
  await expect(result).toContainText('新增候选 1')
  await expect(result).toContainText('导出时间未知')
  await page.locator('.task-row').click()
  const detail = page.getByRole('region', { name: '待办审批详情' })
  await expect(detail).toContainText('优先级：关注 · 内部标签：库存阈值')
  await detail.getByText('查看依据（1 行）').click()
  await detail.getByText(/来源：ops-stock.csv/).click()
  await detail.getByRole('button', { name: '查看来源原始行' }).click()
  await expect(detail.getByRole('region', { name: '来源原始值' })).toContainText('OPS-001')
  await detail.getByLabel('处理备注').fill('合成核对记录')
  await expect(page.getByRole('button', { name: '运行今日运营' })).toBeDisabled()
  await detail.getByRole('button', { name: '批准并创建待办' }).click()
  await expect(detail.getByRole('heading', { name: /事项 #.*待处理/ })).toBeVisible()
  await detail
    .getByLabel('截止时间（含时区偏移，可留空）')
    .fill(new Date(Date.now() + 86400000).toISOString())
  await detail.getByRole('button', { name: '延期至截止时间' }).click()
  await expect(detail.getByRole('heading', { name: /事项 #.*已延期/ })).toBeVisible()
  await detail.getByRole('button', { name: '标记完成' }).click()
  await expect(detail.getByRole('heading', { name: /事项 #.*已完成/ })).toBeVisible()
  await page.getByRole('button', { name: '运行今日运营' }).click()
  await expect(result).toContainText('新增候选 0 · 复用事项 1')
  await expect(page.locator('.task-row')).toHaveCount(1)
  await expect(page.locator('.task-row')).toContainText('已完成')
  await page.locator('.task-row').click()
  await detail.getByRole('button', { name: '重新打开待办' }).click()
  await expect(detail.getByRole('heading', { name: /事项 #.*待处理/ })).toBeVisible()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-operations-desktop.png'),
    fullPage: true,
  })
  await page.reload()
  await page.getByLabel('所属店铺').selectOption(String(shop))
  await page.getByLabel('数据身份').selectOption('synthetic')
  await expect(page.locator('.task-row')).toContainText('待处理')
  const imported = (await (await page.request.get(`/api/imports/${batch}`)).json()) as {
    version: number
  }
  const cleared = await page.request.post(`/api/imports/${batch}/clear`, {
    headers,
    data: { version: imported.version },
  })
  expect(cleared.ok(), await cleared.text()).toBeTruthy()
  await page.getByRole('button', { name: '刷新记录' }).click()
  await expect(result).toContainText('来源已清除')
  await page.locator('.task-row').click()
  await expect(detail).toContainText('处理备注已擦除')
  await expect(detail).not.toContainText('合成核对记录')
  expect(errors).toEqual([])
})

test('mobile empty operations, ignored finding and preserved history', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const { shop, headers } = await setup(page)
  await page.getByRole('button', { name: '运行今日运营' }).click()
  const result = page.getByRole('region', { name: '巡检结果' })
  await expect(result).toContainText('库存未知 / 未检查')
  await expect(page.locator('.task-row')).toHaveCount(0)
  await importInventory(page, shop, headers)
  await page.getByRole('button', { name: '运行今日运营' }).click()
  await page.locator('.task-row').click()
  await page.getByRole('button', { name: '忽略此事项' }).click()
  await expect(page.getByRole('heading', { name: /事项 #.*已忽略/ })).toBeVisible()
  await page.getByRole('button', { name: '运行今日运营' }).click()
  await expect(result).toContainText('新增候选 0 · 复用事项 1')
  await expect(page.locator('.task-row')).toHaveCount(1)
  await expect(page.locator('.task-row')).toContainText('已忽略')
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-operations-mobile.png'),
    fullPage: true,
  })
})
