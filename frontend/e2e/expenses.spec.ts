import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'
import os from 'node:os'

interface Batch {
  id: number
  version: number
  mapping: Record<string, string>
}
const csv =
  'order_id,line_id,sku,quantity,unit_price,currency,ordered_at,status,discount,refund\nO1,1,CUP,2,12.34,USD,2026-10-07 10:00:00,paid,0,0\n'
async function importOrders(
  page: Page,
  headers: Record<string, string>,
  shop: number,
  text = csv,
): Promise<Batch> {
  const uploaded = await page.request.post(`/api/shops/${shop}/imports`, {
    headers,
    params: {
      filename: 'expenses-synthetic.csv',
      kind: 'orders',
      source_channel: 'generic',
      data_identity: 'synthetic',
      timezone: 'Asia/Shanghai',
    },
    data: text,
  })
  expect(uploaded.ok(), await uploaded.text()).toBeTruthy()
  const initial = (await uploaded.json()) as Batch
  const preview = await page.request.post(`/api/imports/${initial.id}/preview`, {
    headers,
    data: { version: initial.version, mapping: initial.mapping },
  })
  expect(preview.ok(), await preview.text()).toBeTruthy()
  const parsed = (await preview.json()) as Batch
  const committed = await page.request.post(`/api/imports/${initial.id}/commit`, {
    headers,
    data: { version: parsed.version, allow_updates: true },
  })
  expect(committed.ok(), await committed.text()).toBeTruthy()
  return (await committed.json()) as Batch
}
async function fillFee(page: Page, reference: string): Promise<void> {
  await page.getByLabel('费用名称', { exact: true }).fill('合成尾程运费')
  await page.getByLabel('费用类别', { exact: true }).selectOption('shipping')
  await page.getByLabel('实际费用金额', { exact: true }).fill('12.3456')
  await page.getByLabel('发生时间（含偏移）', { exact: true }).fill('2026-10-07T08:30:00+08:00')
  await page.getByLabel('发生时区（IANA）', { exact: true }).fill('Asia/Shanghai')
  await page.getByLabel('凭据编号', { exact: true }).fill(reference)
  await page.getByLabel('事实依据', { exact: true }).fill('合成运费收据，确认归属该订单行')
  await page.getByLabel('本次录入或修订理由', { exact: true }).fill('按合成收据核对录入')
}
async function linkOrder(page: Page): Promise<void> {
  await page.getByLabel('费用归属', { exact: true }).selectOption('order_line')
  await page.getByLabel('订单号（精确匹配）', { exact: true }).fill('O1')
  await page.getByRole('button', { name: '查找当前订单行', exact: true }).click()
  const option = page
    .getByLabel('关联订单行', { exact: true })
    .getByRole('option', { name: /O1 \/ 1/ })
  await expect(option).toHaveCount(1)
  await page
    .getByLabel('关联订单行', { exact: true })
    .selectOption({ label: await option.innerText() })
}
async function save(page: Page): Promise<void> {
  await page.getByLabel('我已核对金额、发生时间、凭据和归属，确认保存本版本').check()
  await page.getByRole('button', { name: '确认保存费用', exact: true }).click()
  await expect(page.getByRole('region', { name: '费用录入', exact: true })).toHaveCount(0)
}
for (const mobile of [false, true]) {
  test(`actual expenses evidence, revisions, summary and erase ${mobile ? 'mobile' : 'desktop'}`, async ({
    page,
  }) => {
    await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 })
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.goto('/expenses')
    await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
    await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })
    const session = (await (await page.request.get('/api/auth/session')).json()) as {
      csrf_token: string
    }
    const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
    const response = await page.request.post('/api/shops', {
      headers,
      data: {
        code: `expense-${test.info().testId.slice(-12)}`,
        name: '费用核对合成店',
        platform: 'other',
        market: 'US',
        currency: 'USD',
        timezone: 'Asia/Shanghai',
      },
    })
    expect(response.ok(), await response.text()).toBeTruthy()
    const shop = ((await response.json()) as { id: number }).id
    const source = await importOrders(page, headers, shop)
    await page.goto(`/expenses?shop=${shop}`)
    await expect(page).toHaveURL(new RegExp(`/expenses\\?shop=${shop}$`))
    await expect(page).toHaveTitle(/SoloOps/)
    await expect(page.getByRole('heading', { name: '实际费用，每一笔有依据。' })).toBeVisible()
    await expect(page.locator('vite-error-overlay')).toHaveCount(0)
    await page.screenshot({
      path: path.join(os.tmpdir(), `soloops-expenses-entry-${mobile ? 'mobile' : 'desktop'}.png`),
    })
    await page.getByLabel('数据身份', { exact: true }).selectOption('synthetic')
    await page.getByRole('button', { name: '新增实际费用', exact: true }).click()
    await fillFee(page, 'LOGISTICS-001')
    await linkOrder(page)
    const editor = page.getByRole('region', { name: '费用录入', exact: true })
    await editor.locator('summary').filter({ hasText: '来源：' }).click()
    await editor.getByRole('button', { name: '查看来源原始行' }).click()
    await expect(editor.getByRole('region', { name: '来源原始值' })).toContainText('CUP')
    await page.getByLabel('我已核对金额、发生时间、凭据和归属，确认保存本版本').check()
    await page.getByLabel('实际费用金额', { exact: true }).fill('13.0001')
    await expect(page.getByRole('button', { name: '确认保存费用', exact: true })).toBeDisabled()
    await save(page)
    const detail = page.getByRole('region', { name: '费用详情与版本', exact: true })
    await expect(detail).toContainText('13.0001')
    await page.getByRole('link', { name: '费用固定链接' }).click()
    await page.reload()
    await expect(page.getByLabel('数据身份', { exact: true })).toHaveValue('synthetic')
    await expect(detail).toContainText('订单 O1 / 行 1')
    await detail.getByRole('button', { name: '修订费用', exact: true }).click()
    await expect(page.getByRole('button', { name: '确认保存费用', exact: true })).toBeDisabled()
    await linkOrder(page)
    await page.getByLabel('实际费用金额', { exact: true }).fill('15.6789')
    await page.getByLabel('本次录入或修订理由', { exact: true }).fill('按修订收据更正金额')
    await save(page)
    await expect(detail).toContainText('当前版本 2')
    await detail.getByText('版本历史（2）', { exact: true }).click()
    await expect(detail).toContainText('13.0001')
    await detail.evaluate((e) => e.scrollIntoView({ block: 'start' }))
    await page.screenshot({
      path: path.join(os.tmpdir(), `soloops-expenses-${mobile ? 'mobile' : 'desktop'}.png`),
    })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBeTruthy()
    await page.getByLabel('开始时间（含偏移）', { exact: true }).fill('2026-10-07T00:00:00+08:00')
    await page.getByLabel('结束时间（含偏移）', { exact: true }).fill('2026-10-08T00:00:00+08:00')
    await page.getByRole('button', { name: '核对费用合计', exact: true }).click()
    await expect(page.getByLabel('费用合计结果', { exact: true })).toContainText('15.6789')
    await expect(page.getByLabel('费用合计结果', { exact: true })).toContainText('费用完整性未知')
    await importOrders(page, headers, shop, csv.replace('12.34', '13.34'))
    await page.getByRole('button', { name: '刷新费用', exact: true }).click()
    await expect(detail).toContainText('来源变化 · 待重核')
    await page.getByRole('button', { name: '核对费用合计', exact: true }).click()
    await expect(page.getByLabel('费用合计结果', { exact: true })).toContainText(
      '有效 0 笔 · 待重核 1 笔',
    )
    await detail.getByRole('button', { name: '修订费用', exact: true }).click()
    await page.getByLabel('费用归属', { exact: true }).selectOption('shop')
    await page.getByLabel('本次录入或修订理由', { exact: true }).fill('合成核验：改为店铺公共费用')
    await save(page)
    const clearSource = await page.request.post(`/api/imports/${source.id}/clear`, {
      headers,
      data: { version: source.version },
    })
    expect(clearSource.ok(), await clearSource.text()).toBeTruthy()
    await page.getByRole('button', { name: '刷新费用', exact: true }).click()
    await expect(detail).toContainText('正文已清除')
    await expect(detail).not.toContainText('LOGISTICS-001')
    await expect(detail).not.toContainText('15.6789')
    await page.getByRole('button', { name: '新增实际费用', exact: true }).click()
    await fillFee(page, 'SHOP-002')
    await save(page)
    await detail.getByText('撤销或清除费用', { exact: true }).click()
    await page.getByLabel('确认执行所选费用处理及全部版本影响').check()
    await page.getByRole('button', { name: '执行费用处理', exact: true }).click()
    await expect(detail).toContainText('已撤销')
    await detail.getByText('撤销或清除费用', { exact: true }).click()
    await page.getByLabel('处理方式', { exact: true }).selectOption('clear')
    await expect(page.getByRole('button', { name: '执行费用处理', exact: true })).toBeDisabled()
    await page.getByLabel('确认执行所选费用处理及全部版本影响').check()
    await page.getByRole('button', { name: '执行费用处理', exact: true }).click()
    await expect(detail).toContainText('正文已清除')
    await page.reload()
    await expect(page.getByRole('region', { name: '费用记录列表', exact: true })).not.toContainText(
      'SHOP-002',
    )
    expect(errors).toEqual([])
  })
}
