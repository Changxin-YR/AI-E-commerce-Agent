import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'
import os from 'node:os'

interface Batch {
  id: number
  version: number
  mapping: Record<string, string>
}
async function importProducts(
  page: Page,
  headers: Record<string, string>,
  shop: number,
  content: string,
): Promise<Batch> {
  const uploaded = await page.request.post(`/api/shops/${shop}/imports`, {
    headers,
    params: {
      filename: 'quality-synthetic.csv',
      kind: 'products',
      source_channel: 'generic',
      data_identity: 'synthetic',
      timezone: 'Asia/Shanghai',
    },
    data: content,
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

for (const mobile of [false, true]) {
  const viewport = mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 }

  test(`product quality preview, evidence, save, stale and purge ${mobile ? 'mobile' : 'desktop'}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.goto('/product-quality')
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
        code: `quality-${test.info().testId.slice(-12)}`,
        name: '商品质量合成店',
        platform: 'other',
        market: 'US',
        currency: 'USD',
        timezone: 'Asia/Shanghai',
      },
    })
    expect(response.ok(), await response.text()).toBeTruthy()
    const shop = ((await response.json()) as { id: number }).id
    const csv =
      'sku,name,facts,price,currency,unit_cost,cost_currency\nA,Cup,"Color: red\nColor: blue",0,USD,0,USD\na,TBD,,,,,\n'
    const batch = await importProducts(page, headers, shop, csv)
    await page.goto(`/product-quality?shop=${shop}`)
    await expect(page.getByRole('heading', { name: '商品资料，逐项核对。' })).toBeVisible()
    await page.getByRole('button', { name: '检查商品信息', exact: true }).click()
    await expect(page.getByRole('heading', { name: '此范围暂无商品，未检查' })).toBeVisible()
    await page.getByLabel('数据身份', { exact: true }).selectOption('synthetic')
    await page.getByRole('button', { name: '检查商品信息', exact: true }).click()
    const result = page.getByRole('region', { name: '商品质量检查结果' })
    await expect(result).toContainText('品牌与商品编码 · 未检查')
    await expect(result).toContainText('同名参数出现多个不同值')
    const first = result.getByRole('article', { name: '商品 A', exact: true })
    await expect(first).toContainText('相似 SKU')
    await first.locator('summary').filter({ hasText: '来源：' }).click()
    await first.getByRole('button', { name: '查看来源原始行' }).click()
    await expect(first.getByRole('region', { name: '来源原始值' })).toContainText('Color: red')
    await page.getByLabel('核对项筛选').selectOption('missing')
    await expect(result.getByRole('article')).toHaveCount(1)
    await page.getByLabel('核对项筛选').selectOption('all')
    await page.getByLabel('我已查看范围与未检查项，确认保存本次本地检查报告').check()
    await page.getByRole('button', { name: '保存检查报告', exact: true }).click()
    await expect(page.getByRole('region', { name: '报告存档状态' })).toContainText('来源未变化')
    const link = page.getByRole('link', { name: '报告固定链接' })
    await expect(link).toHaveAttribute('href', /\/product-quality\?shop=\d+&report=\d+/)
    await link.click()
    await page.reload()
    await expect(result.getByRole('article')).toHaveCount(2)
    await expect(page.getByLabel('数据身份', { exact: true })).toHaveValue('synthetic')
    await result.getByRole('heading', { name: '检查结果与依据' }).scrollIntoViewIfNeeded()
    await page.screenshot({
      path: path.join(os.tmpdir(), `soloops-product-quality-${mobile ? 'mobile' : 'desktop'}.png`),
    })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBeTruthy()
    await importProducts(page, headers, shop, csv.replace('Color: blue', 'Color: green'))
    await page.getByRole('button', { name: '刷新报告与来源' }).click()
    await expect(page.getByRole('region', { name: '报告存档状态' })).toContainText(
      '来源已变化，需重新检查',
    )
    const cleared = await page.request.post(`/api/imports/${batch.id}/clear`, {
      headers,
      data: { version: batch.version },
    })
    expect(cleared.ok(), await cleared.text()).toBeTruthy()
    await page.getByRole('button', { name: '刷新报告与来源' }).click()
    await expect(page.getByRole('region', { name: '报告存档状态' })).toContainText('正文已清除')
    await expect(result).toHaveCount(0)
    await page.getByLabel('数据身份', { exact: true }).selectOption('synthetic')
    await page.getByLabel('SKU 前缀（可选）').fill('A')
    await page.getByRole('button', { name: '检查商品信息', exact: true }).click()
    await page.getByLabel('我已查看范围与未检查项，确认保存本次本地检查报告').check()
    await page.getByRole('button', { name: '保存检查报告', exact: true }).click()
    await page.getByLabel('确认清除这份报告正文与来源依赖').check()
    await page.getByRole('button', { name: '清除报告正文', exact: true }).click()
    await expect(page.getByLabel('SKU 前缀（可选）')).toHaveValue('')
    await expect(page.getByRole('region', { name: '报告存档状态' })).toContainText('正文已清除')
    await expect(result).toHaveCount(0)
    expect(errors).toEqual([])
  })
}
