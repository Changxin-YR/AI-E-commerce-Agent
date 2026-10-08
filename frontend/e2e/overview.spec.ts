import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'
import os from 'node:os'

interface Batch {
  id: number
  version: number
  mapping: Record<string, string>
}
async function login(page: Page): Promise<Record<string, string>> {
  await page.goto('/overview')
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
  const session = (await (await page.request.get('/api/auth/session')).json()) as {
    csrf_token: string
  }
  return { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
}
async function shop(
  page: Page,
  headers: Record<string, string>,
  suffix: string,
  market = 'US',
): Promise<number> {
  const response = await page.request.post('/api/shops', {
    headers,
    data: {
      code: `ov-${test.info().testId.slice(-12)}-${suffix.toLowerCase()}`,
      name: `总览合成店 ${suffix}`,
      platform: 'other',
      market,
      currency: 'USD',
      timezone: 'Asia/Shanghai',
    },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return ((await response.json()) as { id: number }).id
}
async function importFile(
  page: Page,
  headers: Record<string, string>,
  id: number,
  kind: string,
  csv: string,
): Promise<Batch> {
  const uploaded = await page.request.post(`/api/shops/${id}/imports`, {
    headers,
    params: {
      filename: 'overview-synthetic.csv',
      kind,
      source_channel: 'generic',
      data_identity: 'synthetic',
      timezone: 'Asia/Shanghai',
    },
    data: csv,
  })
  expect(uploaded.ok(), await uploaded.text()).toBeTruthy()
  const batch = (await uploaded.json()) as Batch
  const preview = await page.request.post(`/api/imports/${batch.id}/preview`, {
    headers,
    data: { version: batch.version, mapping: batch.mapping },
  })
  expect(preview.ok(), await preview.text()).toBeTruthy()
  const parsed = (await preview.json()) as Batch
  const committed = await page.request.post(`/api/imports/${batch.id}/commit`, {
    headers,
    data: { version: parsed.version, allow_updates: true },
  })
  expect(committed.ok(), await committed.text()).toBeTruthy()
  return (await committed.json()) as Batch
}
async function range(page: Page): Promise<void> {
  await page.getByLabel('数据身份').selectOption('synthetic')
  await page.getByLabel('日期快捷范围').selectOption('custom')
  await page.getByLabel('开始日期（计入）', { exact: true }).fill('2026-10-07')
  await page.getByLabel('结束日期（不计入）', { exact: true }).fill('2026-10-08')
}
async function only(page: Page, names: string[]): Promise<void> {
  await expect(page.getByLabel(names[0]!, { exact: false })).toBeEnabled()
  const boxes = page.locator('.shop-options input')
  for (const box of await boxes.all()) await box.uncheck()
  for (const name of names) await page.getByLabel(name, { exact: false }).check()
}

test('cross shop overview, source review, saved refresh and dependent purge', async ({ page }) => {
  const headers = await login(page)
  const first = await shop(page, headers, 'A')
  const second = await shop(page, headers, 'B', 'GB')
  const product = 'sku,name,unit_cost,cost_currency\nA,Synthetic cup,7.125,USD\n'
  await importFile(page, headers, first, 'products', product)
  const header =
    'order_id,line_id,sku,quantity,unit_price,currency,ordered_at,status,discount,refund,fulfillment_status\n'
  const batch = await importFile(
    page,
    headers,
    first,
    'orders',
    header +
      'O1,1,A,2,19.99,USD,2026-10-07 08:00:00,paid,1,0,unfulfilled\nP1,1,A,1,10,USD,2026-10-06 08:00:00,paid,0,0,fulfilled\n',
  )
  await importFile(
    page,
    headers,
    second,
    'orders',
    header +
      'O1,1,A,1,20,USD,2026-10-07 08:00:00,paid,0,0,fulfilled\nE1,1,A,1,100,EUR,2026-10-07 08:00:00,paid,0,0,fulfilled\n',
  )
  await page.goto('/overview')
  const errors: string[] = []
  page.on('pageerror', (err) => errors.push(err.message))
  await expect(page.getByRole('heading', { name: '看清每家店，再做下一步。' })).toBeVisible()
  await only(page, ['总览合成店 A', '总览合成店 B'])
  await range(page)
  await page.screenshot({
    path: path.join(os.tmpdir(), 'soloops-overview-form-desktop.png'),
    fullPage: true,
  })
  await page.getByRole('button', { name: '生成经营总览', exact: true }).click()
  const result = page.getByRole('region', { name: '经营总览结果', exact: true })
  await expect(result.getByRole('article', { name: 'USD 汇总' })).toContainText('58.9800')
  await expect(result.getByRole('article', { name: 'EUR 汇总' })).toContainText('100.0000')
  const firstCard = result.getByRole('article', { name: '总览合成店 A', exact: true })
  await firstCard.getByRole('button', { name: '查看本期 USD 订单依据' }).click()
  await firstCard.getByText('O1 / 1 · A · 计入 · paid', { exact: true }).click()
  await firstCard.getByRole('button', { name: /订单来源/ }).click()
  await expect(firstCard.getByRole('region', { name: '来源原始值' })).toContainText(
    '"unit_price": "19.9900"',
  )
  await page.getByRole('button', { name: '保存本地摘要' }).click()
  await expect(page.getByText('摘要已保存，可刷新后回读。库存按保存时刻再次核验。')).toBeVisible()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: path.join(os.tmpdir(), 'soloops-overview-first-desktop.png') })
  await page.screenshot({
    path: path.join(os.tmpdir(), 'soloops-overview-desktop.png'),
    fullPage: true,
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: path.join(os.tmpdir(), 'soloops-overview-first-mobile.png') })
  await page.screenshot({
    path: path.join(os.tmpdir(), 'soloops-overview-mobile.png'),
    fullPage: true,
  })
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBeTruthy()
  await page.reload()
  await page
    .getByRole('button', { name: /查看摘要 #/ })
    .first()
    .click()
  await expect(result.getByRole('article', { name: 'USD 汇总' })).toContainText('58.9800')
  const revoked = await page.request.post(`/api/imports/${batch.id}/revoke`, {
    headers,
    data: { version: batch.version },
  })
  expect(revoked.ok(), await revoked.text()).toBeTruthy()
  await page.getByRole('button', { name: '刷新摘要与来源状态' }).click()
  await expect(result.getByRole('alert')).toContainText('历史来源或库存时效已变化')
  const current = (await revoked.json()) as Batch
  const cleared = await page.request.post(`/api/imports/${batch.id}/clear`, {
    headers,
    data: { version: current.version },
  })
  expect(cleared.ok(), await cleared.text()).toBeTruthy()
  await page.getByRole('button', { name: '刷新摘要与来源状态' }).click()
  await expect(page.getByRole('heading', { name: /摘要 #.*正文已清除/ })).toBeVisible()
  await expect(result).toHaveCount(0)
  expect(errors).toEqual([])
})

test('mobile empty coverage, date presets, market filter and clear', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const headers = await login(page)
  await shop(page, headers, 'Empty', 'CA')
  await page.goto('/overview')
  await page.getByLabel('市场筛选').selectOption('CA')
  await only(page, ['总览合成店 Empty'])
  await page.getByLabel('日期快捷范围').selectOption('1')
  await page.getByRole('button', { name: '生成经营总览', exact: true }).click()
  const result = page.getByRole('region', { name: '经营总览结果', exact: true })
  await expect(result).toContainText('日报')
  await expect(result).toContainText('未知 / 不完整')
  await expect(result).toContainText('当前库存 · 已知低库存 未知')
  await page.getByRole('button', { name: '保存本地摘要' }).click()
  await page.getByLabel(/清除摘要 #.*的正文/).check()
  await page.getByRole('button', { name: '清除所选摘要正文' }).click()
  await expect(result).toHaveCount(0)
  await expect(page.getByRole('heading', { name: /正文已清除/ })).toBeVisible()
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBeTruthy()
})
