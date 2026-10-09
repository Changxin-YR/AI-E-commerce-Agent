import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'
import os from 'node:os'

interface Batch {
  id: number
  version: number
  mapping: Record<string, string>
}
const csv =
  'sku,name,facts,price,currency,unit_cost,cost_currency\nA,Cup,Steel,12.3456,USD,0,USD\nB,Plate,Round,,,,\n'
async function importProducts(
  page: Page,
  headers: Record<string, string>,
  shop: number,
  content = csv,
): Promise<Batch> {
  const upload = await page.request.post(`/api/shops/${shop}/imports`, {
    headers,
    params: {
      filename: 'edits-synthetic.csv',
      kind: 'products',
      source_channel: 'generic',
      data_identity: 'synthetic',
      timezone: 'Asia/Shanghai',
    },
    data: content,
  })
  expect(upload.ok(), await upload.text()).toBeTruthy()
  const batch = (await upload.json()) as Batch
  const preview = await page.request.post(`/api/imports/${batch.id}/preview`, {
    headers,
    data: { version: batch.version, mapping: batch.mapping },
  })
  expect(preview.ok(), await preview.text()).toBeTruthy()
  const parsed = (await preview.json()) as Batch
  const commit = await page.request.post(`/api/imports/${batch.id}/commit`, {
    headers,
    data: { version: parsed.version, allow_updates: true },
  })
  expect(commit.ok(), await commit.text()).toBeTruthy()
  return (await commit.json()) as Batch
}
async function prepare(page: Page, title = 'Updated Cup'): Promise<void> {
  await page.getByRole('button', { name: '加载当前商品', exact: true }).click()
  await page.getByRole('checkbox', { name: /^选择 A ·/ }).check()
  await page.getByRole('checkbox', { name: /^选择 B ·/ }).check()
  await page.getByText('为选中商品填写相同改动', { exact: true }).click()
  await page.getByLabel('名称前缀', { exact: true }).fill('Checked ')
  await page.getByRole('button', { name: '填入选中商品', exact: true }).click()
  await expect(page.getByLabel('商品 B 名称', { exact: true })).toHaveValue(/^Checked /)
  await page.getByLabel('商品 A 名称', { exact: true }).fill(title)
  await page.getByLabel('商品 B 参数', { exact: true }).fill('Shape: Round\nColor: Blue')
  await page.getByLabel('修订依据', { exact: true }).fill('合成规格表已核对')
  await page.getByRole('button', { name: '保存修订草稿', exact: true }).click()
  await expect(page.getByRole('region', { name: '修订差异与审批' })).toContainText('待审批草稿')
}
async function approve(page: Page): Promise<void> {
  await page.getByLabel('我已逐项核对差异与事实依据，批准本批本地生效').check()
  await page.getByRole('button', { name: '批准本地生效', exact: true }).click()
}
for (const mobile of [false, true]) {
  test(`local product edits approval, conflict, revoke and clear ${mobile ? 'mobile' : 'desktop'}`, async ({
    page,
  }) => {
    await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 })
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.goto('/product-edits')
    await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
    await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
    // The initial unauthenticated session probe returns 401; inspect console health after login.
    page.on('console', (message) => {
      if (message.type() === 'error') errors.push(message.text())
    })
    const session = (await (await page.request.get('/api/auth/session')).json()) as {
      csrf_token: string
    }
    const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
    const response = await page.request.post('/api/shops', {
      headers,
      data: {
        code: `edits-${test.info().testId.slice(-12)}`,
        name: '商品修订合成店',
        platform: 'other',
        market: 'US',
        currency: 'USD',
        timezone: 'Asia/Shanghai',
      },
    })
    expect(response.ok(), await response.text()).toBeTruthy()
    const shop = ((await response.json()) as { id: number }).id
    const origin = await importProducts(page, headers, shop)
    await page.goto(`/product-edits?shop=${shop}`)
    await expect(page).toHaveURL(new RegExp(`/product-edits\\?shop=${shop}$`))
    await expect(page).toHaveTitle(/SoloOps/)
    await expect(page.getByRole('heading', { name: '商品修订，核对后生效。' })).toBeVisible()
    await expect(page.locator('vite-error-overlay')).toHaveCount(0)
    await page.screenshot({
      path: path.join(
        os.tmpdir(),
        `soloops-product-edits-entry-${mobile ? 'mobile' : 'desktop'}.png`,
      ),
    })
    await page.getByRole('button', { name: '加载当前商品', exact: true }).click()
    await expect(page.getByText('此范围暂无商品，请导入资料或调整范围。')).toBeVisible()
    await page.getByLabel('数据身份', { exact: true }).selectOption('synthetic')
    await prepare(page)
    const review = page.getByRole('region', { name: '修订差异与审批' })
    await expect(page.getByRole('button', { name: '批准本地生效', exact: true })).toBeDisabled()
    await review
      .getByRole('article', { name: '修订 A', exact: true })
      .locator('summary')
      .filter({ hasText: '来源：' })
      .click()
    await review
      .getByRole('article', { name: '修订 A', exact: true })
      .getByRole('button', { name: '查看来源原始行' })
      .click()
    await expect(review.getByRole('region', { name: '来源原始值' })).toContainText('Steel')
    await page.getByRole('link', { name: '修订固定链接' }).click()
    await page.reload()
    await expect(page.getByLabel('数据身份', { exact: true })).toHaveValue('synthetic')
    await expect(review).toContainText('Updated Cup')
    await review
      .getByRole('article', { name: '修订 A', exact: true })
      .evaluate((element) => element.scrollIntoView({ block: 'start' }))
    await page.screenshot({
      path: path.join(os.tmpdir(), `soloops-product-edits-${mobile ? 'mobile' : 'desktop'}.png`),
    })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBeTruthy()
    await approve(page)
    await expect(review).toContainText('本地已生效')
    await expect(review).toContainText('当前 2 项仍为主档来源')
    const current = await page.request.post(`/api/shops/${shop}/product-quality/preview`, {
      headers,
      data: { data_identity: 'synthetic' },
    })
    const products = (
      (await current.json()) as {
        products: { name: string; price: string; source: { origin: string } }[]
      }
    ).products
    expect(products[0]?.name).toBe('Updated Cup')
    expect(products[0]?.price).toBe('12.3456')
    expect(products[0]?.source.origin).toBe('manual_edit')
    await page.getByText('拒绝、撤销与清除', { exact: true }).click()
    await page.getByLabel('处理方式', { exact: true }).selectOption('withdraw')
    await page.getByLabel('确认执行所选处理及其依赖影响').check()
    await page.getByRole('button', { name: '执行所选处理' }).click()
    await expect(review).toContainText('已撤销')
    await prepare(page, 'Conflict Cup')
    const newer = await importProducts(page, headers, shop, csv.replace('A,Cup', 'A,Fresh Cup'))
    await approve(page)
    await expect(review).toContainText('整批未生效')
    await expect(review.getByRole('article', { name: '修订 A', exact: true })).toContainText(
      '商品或来源已变化',
    )
    await prepare(page, 'Final Cup')
    await approve(page)
    await expect(review).toContainText('本地已生效')
    const cleared = await page.request.post(`/api/imports/${newer.id}/clear`, {
      headers,
      data: { version: newer.version },
    })
    expect(cleared.ok(), await cleared.text()).toBeTruthy()
    await page.getByRole('button', { name: '刷新修订与来源' }).click()
    await expect(review).toContainText('正文已清除')
    await expect(review.getByRole('article')).toHaveCount(0)
    // The original independent file remains usable after clearing the later branch.
    const batch = (await (await page.request.get(`/api/imports/${origin.id}`)).json()) as Batch
    expect(batch.id).toBe(origin.id)
    await prepare(page, 'Manual Clear Cup')
    await page.getByText('拒绝、撤销与清除', { exact: true }).click()
    await page.getByLabel('确认执行所选处理及其依赖影响').check()
    await page.getByRole('button', { name: '执行所选处理' }).click()
    await expect(review).toContainText('正文已清除')
    expect(errors).toEqual([])
  })
}
