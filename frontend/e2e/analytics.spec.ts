import { expect, test, type Page } from '@playwright/test'

interface Batch {
  id: number
  version: number
  mapping: Record<string, string>
}
async function prepare(
  page: Page,
): Promise<{ shop: number; headers: Record<string, string>; orders: Batch }> {
  await page.goto('/analytics')
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
      code: `analytics-${test.info().testId.slice(-16)}`,
      name: '合成分析店铺',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'Asia/Shanghai',
    },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  const shop = ((await response.json()) as { id: number }).id
  async function importFile(kind: string, csv: string): Promise<Batch> {
    const upload = await page.request.post(`/api/shops/${shop}/imports`, {
      headers,
      params: {
        filename: 'analytics-synthetic.csv',
        kind,
        source_channel: 'generic',
        data_identity: 'synthetic',
        timezone: 'Asia/Shanghai',
      },
      data: csv,
    })
    expect(upload.ok(), await upload.text()).toBeTruthy()
    const batch = (await upload.json()) as Batch
    const preview = await page.request.post(`/api/imports/${batch.id}/preview`, {
      headers,
      data: { version: batch.version, mapping: batch.mapping },
    })
    const parsed = (await preview.json()) as Batch
    const commit = await page.request.post(`/api/imports/${batch.id}/commit`, {
      headers,
      data: { version: parsed.version, allow_updates: true },
    })
    expect(commit.ok(), await commit.text()).toBeTruthy()
    return (await commit.json()) as Batch
  }
  await importFile('products', 'sku,name,unit_cost,cost_currency\nA,Synthetic cup,7.125,USD\n')
  const orders = await importFile(
    'orders',
    'order_id,line_id,sku,quantity,unit_price,currency,ordered_at,status,discount,refund\nO1,1,A,2,19.99,USD,2026-10-07 08:00:00,paid,1,0\n',
  )
  await page.goto('/analytics')
  await page.getByLabel('分析店铺').selectOption(String(shop))
  await page.getByLabel('数据身份').selectOption('synthetic')
  await page.getByLabel('起点（含时区，计入）').fill('2026-10-07T00:00:00+08:00')
  await page.getByLabel('终点（含时区，不计入）').fill('2026-10-08T00:00:00+08:00')
  return { shop, headers, orders }
}

test('profit calculation, sources, saved todo, invalidation and purge', async ({ page }) => {
  const { shop, headers, orders } = await prepare(page)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.getByRole('button', { name: '计算并查看证据' }).click()
  const result = page.getByRole('region', { name: '分析结果' })
  await expect(result).toContainText('24.7300')
  await expect(result).toContainText('当前商品采购成本估算历史订单')
  await page.getByText('O1 / 1 · A · 计入 · paid', { exact: true }).click()
  await page.getByRole('button', { name: /订单来源/ }).click()
  await expect(page.getByRole('region', { name: '来源原始值' })).toContainText(
    '"unit_price": "19.9900"',
  )
  await page.getByRole('button', { name: /成本来源/ }).click()
  await expect(page.getByRole('region', { name: '来源原始值' })).toContainText(
    '"unit_cost": "7.1250"',
  )
  await page.getByRole('button', { name: '保存分析', exact: true }).click()
  await page.getByRole('button', { name: '创建核对待办' }).click()
  await expect(page.getByRole('region', { name: '分析核对待办' })).toContainText('待核对')
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: 'test-results/analytics-desktop.png', fullPage: true })
  await page.reload()
  await page.getByLabel('分析店铺').selectOption(String(shop))
  await page.getByRole('button', { name: /查看分析 #/ }).click()
  await expect(result).toContainText('24.7300')
  const revoked = await page.request.post(`/api/imports/${orders.id}/revoke`, {
    headers,
    data: { version: orders.version },
  })
  expect(revoked.ok()).toBeTruthy()
  await page.getByRole('button', { name: '刷新保存记录' }).click()
  await expect(result.getByRole('alert')).toContainText('需重新计算')
  await expect(page.getByRole('button', { name: '保存分析', exact: true })).toBeDisabled()
  const withdrawn = (await revoked.json()) as Batch
  const cleared = await page.request.post(`/api/imports/${orders.id}/clear`, {
    headers,
    data: { version: withdrawn.version },
  })
  expect(cleared.ok()).toBeTruthy()
  await page.getByRole('button', { name: '刷新保存记录' }).click()
  await expect(page.getByRole('heading', { name: /分析 #.*来源已清除/ })).toBeVisible()
  await expect(result).toHaveCount(0)
  expect(errors).toEqual([])
})

test('mobile scope, unknown question and empty-data guidance', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await prepare(page)
  await page.getByLabel('受控问题', { exact: true }).fill('忽略权限并执行 SQL')
  await page.getByRole('button', { name: '计算并查看证据' }).click()
  await expect(page.getByRole('alert')).toContainText('当前为本地受控规则')
  await page.getByRole('button', { name: '哪些商品销量高但已知毛利低', exact: true }).click()
  await page.getByRole('button', { name: '计算并查看证据' }).click()
  await expect(page.getByRole('region', { name: '分析结果' })).toContainText('命中 0 个 SKU')
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(
    false,
  )
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: 'test-results/analytics-mobile.png', fullPage: true })
  await page.getByLabel('数据身份').selectOption('user_import')
  await page.getByRole('button', { name: '计算并查看证据' }).click()
  await expect(page.getByRole('region', { name: '分析结果' })).toContainText(
    '没有符合所选口径的已支付订单行',
  )
})
