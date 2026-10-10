import { expect, test, type Page } from '@playwright/test'
import { createHash } from 'node:crypto'
import type { ImportBatch } from '../src/types/imports'
import type { ImportGroup } from '../src/types/imports'

async function openImports(page: Page): Promise<number> {
  await page.goto('/imports')
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
  // Fixture setup uses the same authenticated API as the shop form.
  const session = (await (await page.request.get('/api/auth/session')).json()) as {
    csrf_token: string
  }
  const response = await page.request.post('/api/shops', {
    headers: { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token },
    data: {
      code: `import-${test.info().testId.slice(-16)}`,
      name: '合成导入店铺',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'Asia/Shanghai',
    },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  const shop = (await response.json()) as { id: number }
  await page.goto('/imports')
  await page.getByLabel('所属店铺').selectOption(String(shop.id))
  await page.getByLabel('数据身份').selectOption('synthetic')
  return shop.id
}

async function uploadCsv(page: Page, contents: string): Promise<void> {
  await page
    .getByLabel('CSV / Excel 文件')
    .setInputFiles({ name: 'synthetic.csv', mimeType: 'text/csv', buffer: Buffer.from(contents) })
  await page.getByRole('button', { name: '上传并查看映射' }).click()
  await expect(page.getByRole('heading', { name: '02 / 核对字段映射' })).toBeVisible()
}

test('seller maps unknown columns, corrects a row, imports, reloads, revokes and clears', async ({
  page,
}) => {
  const shopId = await openImports(page)
  await uploadCsv(page, 'code,label,cost,currency\n001,Synthetic cup,-3,USD\n')
  await page.getByLabel('SKU *', { exact: true }).selectOption('code')
  await page.getByLabel('商品名 *', { exact: true }).selectOption('label')
  await page.getByLabel('单位采购成本', { exact: true }).selectOption('cost')
  await page.getByLabel('销售币种', { exact: true }).selectOption('')
  await page.getByLabel('成本币种', { exact: true }).selectOption('currency')
  await page.getByLabel('保存为个人映射').fill('合成自定义商品')
  await page.getByRole('button', { name: '保存映射', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('个人映射模板已保存')
  await page.getByRole('button', { name: '校验并预览' }).click()
  await expect(page.getByText('需修正', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
  await page.getByLabel('源行 2 单位采购成本 修正值').fill('3.25')
  await page.getByRole('button', { name: '校验并预览' }).click()
  await expect(page.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
  for (const checkbox of await page
    .getByRole('group', { name: '确认关键字段含义' })
    .getByRole('checkbox')
    .all())
    await checkbox.check()
  await expect(page.getByRole('button', { name: '确认导入', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '确认导入', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('批次已导入')
  await page.getByText('源行 2 · 001').click()
  await expect(page.getByRole('cell', { name: '3.2500', exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/import-desktop.png', fullPage: true })
  await page.reload()
  await page.getByLabel('所属店铺').selectOption(String(shopId))
  await expect(page.getByRole('button', { name: /查看批次/ })).toHaveCount(1)
  await page.getByRole('button', { name: /查看批次/ }).click()
  await expect(page.getByText('已导入', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '撤销此批次' }).click()
  await page.getByRole('button', { name: '确认撤销' }).click()
  await expect(page.getByText('已撤销', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '清除源数据' }).click()
  await page.getByRole('button', { name: '确认清除' }).click()
  await expect(page.getByText('已清除', { exact: true })).toBeVisible()
  await expect(page.getByText('源行 2 · 001')).toHaveCount(0)
})

test('mobile order preview exposes duplicate rows and fits the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openImports(page)
  await page.getByLabel('报表类型').selectOption('orders')
  const row = 'O1,1,A,1,10,USD,2026-10-07 08:00:00,paid\n'
  await uploadCsv(
    page,
    `order_id,line_id,sku,quantity,unit_price,currency,ordered_at,status\n${row}${row}`,
  )
  await page.getByRole('button', { name: '校验并预览' }).click()
  await expect(page.getByText('需修正', { exact: true })).toHaveCount(2)
  await expect(page.getByRole('link', { name: '下载错误行报告' })).toBeVisible()
  await expect(page.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
  const overflows = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  )
  expect(overflows).toBe(false)
  await page.screenshot({ path: 'test-results/import-mobile.png', fullPage: true })
  await page.getByRole('button', { name: '取消此批次' }).click()
  await page.getByRole('button', { name: '确认撤销' }).click()
  await expect(page.getByText('已撤销', { exact: true })).toBeVisible()
})

for (const { width, amountColumn } of [
  { width: 1440, amountColumn: 'total' },
  { width: 390, amountColumn: `total_${'x'.repeat(90)}` },
]) {
  test(`seller reviews amount meaning and reconciles saved multi-SKU orders at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 })
    const shopId = await openImports(page)
    await page.getByLabel('报表类型').selectOption('orders')
    await uploadCsv(
      page,
      `order_id,line_id,sku,quantity,${amountColumn},currency,ordered_at,status,discount,refund\n` +
        'SYN-R2,001,A,2,20,USD,2026-10-07T00:30:00Z,partially_refunded,2,3\n' +
        'SYN-R2,002,B,3,4,USD,2026-10-07T08:30:00+08:00,paid,0,0\n',
    )
    await page.getByLabel('成交单价 *', { exact: true }).selectOption(amountColumn)
    await page.getByRole('button', { name: '校验并预览' }).click()
    const review = page.getByRole('checkbox', { name: new RegExp(`已核对 ${amountColumn}`) })
    await expect(review).not.toBeChecked()
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
    ).toBe(false)
    await page
      .getByRole('group', { name: '确认关键字段含义' })
      .screenshot({ path: `test-results/r2-review-${width}.png` })
    await expect(page.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
    await review.check()
    // The seller checks the source: row 2 contained a line total, so unit price needs correction.
    await page.getByText('源行 2 · A').click()
    await page.getByLabel('源行 2 成交单价 修正值').fill('10')
    await expect(review).not.toBeChecked()
    await expect(page.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
    await page.getByRole('button', { name: '校验并预览' }).click()
    await expect(review).toBeEnabled()
    await expect(review).not.toBeChecked()
    await review.check()
    const savedResponse = page.waitForResponse(
      (response) => response.url().endsWith('/commit') && response.request().method() === 'POST',
    )
    await page.getByRole('button', { name: '确认导入', exact: true }).click()
    const saved = (await (await savedResponse).json()) as ImportBatch
    expect(saved.status).toBe('committed')
    expect([saved.total_rows, saved.valid_rows, saved.new_rows, saved.error_rows]).toEqual([
      2, 2, 2, 0,
    ])
    expect(saved.rows[0]?.raw.unit_price).toBe('20')
    expect(saved.rows[0]?.corrections.unit_price).toBe('10')
    expect(saved.rows.map((row) => row.normalized.unit_price)).toEqual(['10.0000', '4.0000'])
    const netSales = saved.rows.reduce(
      (sum, row) =>
        sum +
        Number(row.normalized.unit_price) * Number(row.normalized.quantity) -
        Number(row.normalized.discount) -
        Number(row.normalized.refund),
      0,
    )
    expect(netSales).toBe(27)
    await page.reload()
    await page.getByLabel('所属店铺').selectOption(String(shopId))
    await page.getByRole('button', { name: `查看批次 #${saved.id}` }).click()
    await expect(page.getByText('已导入', { exact: true })).toBeVisible()
    const readback = (await (
      await page.request.get(`/api/imports/${saved.id}`)
    ).json()) as ImportBatch
    expect(readback.rows).toEqual(saved.rows)
    await page.getByText('源行 2 · A').click()
    await expect(page.getByRole('cell', { name: '10.0000', exact: true })).toBeVisible()
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
    ).toBe(false)
    await page.screenshot({ path: `test-results/r2-import-${width}.png`, fullPage: true })
  })
}

for (const width of [1440, 390]) {
  test(`large import group resumes and reconciles 2002 source records at ${width}px`, async ({
    page,
  }) => {
    test.setTimeout(60000)
    await page.setViewportSize({ width, height: 900 })
    const shop = await openImports(page)
    await page.getByLabel('报表类型').selectOption('orders')
    const header =
      'order_id,line_id,sku,quantity,unit_price,currency,ordered_at,status,discount,refund\n'
    const row = (i: number) =>
      `O${Math.floor(i / 2)},${(i % 2) + 1},S${i % 2},1,2,USD,2026-10-07T00:00:00Z,paid,0,0\n`
    const parts = [
      Buffer.from(header + Array.from({ length: 2000 }, (_, i) => row(i)).join('')),
      Buffer.from(header + row(2000) + row(0)),
    ]
    const manifest = {
      format: 'soloops-split-v1',
      source_filename: 'synthetic-large.csv',
      source_sha256: createHash('sha256').update(Buffer.concat(parts)).digest('hex'),
      total_rows: 2002,
      parts: parts.map((part, i) => ({
        filename: `part-00${i + 1}.csv`,
        bytes: part.length,
        rows: i === 0 ? 2000 : 2,
        sha256: createHash('sha256').update(part).digest('hex'),
      })),
    }
    await page.getByLabel('拆分清单 manifest.json').setInputFiles({
      name: 'manifest.json',
      mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify(manifest)),
    })
    await page.getByRole('button', { name: '按当前来源建立导入组' }).click()
    await expect(page.getByTestId('group-coverage')).toContainText('部分覆盖／数据不足')
    const groups = (await (
      await page.request.get(`/api/shops/${shop}/import-groups`)
    ).json()) as ImportGroup[]
    const group = groups[0]!
    const session = (await (await page.request.get('/api/auth/session')).json()) as {
      csrf_token: string
    }
    const analysis = () =>
      page.request.post(`/api/shops/${shop}/analytics/calculate`, {
        headers: { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token },
        data: {
          start_at: '2026-10-07T00:00:00Z',
          end_at: '2026-10-08T00:00:00Z',
          timezone: 'UTC',
          currency: 'USD',
          data_identity: 'synthetic',
        },
      })
    expect((await analysis()).status()).toBe(409)
    await page
      .getByLabel('选择原分片 CSV')
      .setInputFiles({ name: 'part-001.csv', mimeType: 'text/csv', buffer: parts[0]! })
    await page.getByRole('button', { name: '上传此分片并核对' }).click()
    await page.getByRole('button', { name: '校验并预览' }).click()
    await page.getByRole('button', { name: '确认导入', exact: true }).click()
    await expect(page.getByTestId('group-coverage')).toContainText('源记录 2000/2002')
    await page.reload()
    await page.getByLabel('所属店铺').selectOption(String(shop))
    await page.getByLabel('继续导入组').selectOption(String(group.id))
    await expect(page.getByTestId('group-coverage')).toContainText('源记录 2000/2002')
    await page
      .getByLabel('选择原分片 CSV')
      .setInputFiles({ name: 'part-002.csv', mimeType: 'text/csv', buffer: parts[1]! })
    await page.getByRole('button', { name: '上传此分片并核对' }).click()
    await page.getByRole('button', { name: '校验并预览' }).click()
    await page.getByRole('button', { name: '确认导入', exact: true }).click()
    await expect(page.getByTestId('group-coverage')).toContainText('分片全部完成')
    await expect(page.getByTestId('group-coverage')).toContainText('去重后 2001；跨片重叠 1')
    const result = await analysis()
    expect(result.ok(), await result.text()).toBeTruthy()
    expect(Number((await result.json()).summary.sales)).toBe(4002)
    await page.getByRole('button', { name: '上传此分片并核对' }).click()
    await expect(page.getByTestId('group-coverage')).toContainText('源记录 2002/2002')
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
    ).toBe(false)
    await page.getByTestId('group-coverage').scrollIntoViewIfNeeded()
    await page.screenshot({ path: `test-results/r2-groups-${width}.png`, fullPage: true })
    await page.getByRole('button', { name: '撤销整组', exact: true }).click()
    await page.getByRole('button', { name: '继续保留' }).click()
    await expect(page.getByTestId('group-coverage')).toContainText('分片全部完成')
    await page.getByRole('button', { name: '撤销整组', exact: true }).click()
    await page.getByRole('button', { name: '确认撤销整组' }).click()
    await expect(page.getByTestId('group-coverage')).toContainText('已整组撤销')
    const afterRevoke = await analysis()
    expect(afterRevoke.ok(), await afterRevoke.text()).toBeTruthy()
    const empty = await afterRevoke.json()
    expect(empty.summary.line_count).toBe(0)
    expect(Number(empty.summary.known_sales_subtotal)).toBe(0)
  })
}
