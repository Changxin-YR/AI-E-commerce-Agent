import { expect, test, type Page } from '@playwright/test'

async function openImports(page: Page): Promise<void> {
  await page.goto('/imports')
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '把经营的第一步，准备好。' })).toBeVisible()
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
  await openImports(page)
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
  await expect(page.getByRole('button', { name: '确认导入', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '确认导入', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('批次已导入')
  await page.getByText('源行 2 · 001').click()
  await expect(page.getByRole('cell', { name: '3.2500', exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/import-desktop.png', fullPage: true })
  await page.reload()
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
