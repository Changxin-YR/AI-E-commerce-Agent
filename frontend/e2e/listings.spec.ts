import { expect, test, type Page } from '@playwright/test'

interface Batch {
  id: number
  version: number
  mapping: Record<string, string>
}
async function prepare(
  page: Page,
  facts = 'Steel',
): Promise<{ shop: number; batch: Batch; headers: Record<string, string> }> {
  await page.goto('/listings')
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
  const session = (await (await page.request.get('/api/auth/session')).json()) as {
    csrf_token: string
  }
  const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
  const shopResponse = await page.request.post('/api/shops', {
    headers,
    data: {
      code: `listing-${test.info().testId.slice(-16)}`,
      name: '合成文案店铺',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'Asia/Shanghai',
    },
  })
  expect(shopResponse.ok(), await shopResponse.text()).toBeTruthy()
  const shop = ((await shopResponse.json()) as { id: number }).id
  const upload = await page.request.post(`/api/shops/${shop}/imports`, {
    headers,
    params: {
      filename: 'listing-synthetic.csv',
      kind: 'products',
      source_channel: 'generic',
      data_identity: 'synthetic',
      timezone: 'Asia/Shanghai',
    },
    data: `sku,name,facts\nA,Synthetic cup,${facts}\n`,
  })
  expect(upload.ok(), await upload.text()).toBeTruthy()
  const uploaded = (await upload.json()) as Batch
  const preview = await page.request.post(`/api/imports/${uploaded.id}/preview`, {
    headers,
    data: { version: uploaded.version, mapping: uploaded.mapping },
  })
  const parsed = (await preview.json()) as Batch
  const commit = await page.request.post(`/api/imports/${uploaded.id}/commit`, {
    headers,
    data: { version: parsed.version, allow_updates: true },
  })
  expect(commit.ok(), await commit.text()).toBeTruthy()
  const batch = (await commit.json()) as Batch
  await page.goto('/listings')
  await page.getByLabel('Listing 店铺').selectOption(String(shop))
  await page.getByRole('button', { name: /A · Synthetic cup/ }).click()
  return { shop, batch, headers }
}

test('product-only draft, edit, approve, restore, reject and source cleanup', async ({ page }) => {
  const { batch, headers, shop } = await prepare(page)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.getByRole('button', { name: '从商品事实生成草稿' }).click()
  const review = page.getByRole('region', { name: 'Listing 审批详情' })
  await expect(review).toContainText('本地事实模板')
  await expect(page.getByRole('region', { name: '当前商品' })).toContainText('尚无已批准版本')
  await review.getByText('事实依据与检查结果', { exact: true }).click()
  await review.getByRole('button', { name: /查看来源原始行/ }).click()
  await expect(review.getByRole('region', { name: '来源原始值' })).toContainText('Steel')
  await review.getByLabel('拟议标题').fill('Synthetic cup · Steel')
  await expect(review.getByRole('button', { name: '批准并在本地生效' })).toBeDisabled()
  await review.getByRole('button', { name: '保存为新待审版本' }).click()
  await expect(review).toContainText('版本 2 · 等待审批')
  await expect(review.getByRole('region', { name: '修改前', exact: true })).toContainText(
    'Synthetic cup',
  )
  await expect(review.getByRole('region', { name: '拟议版本', exact: true })).toContainText(
    'Synthetic cup · Steel',
  )
  await review.getByLabel('我已逐项核对商品事实、差异与影响范围').check()
  await review.getByRole('button', { name: '批准并在本地生效' }).click()
  await expect(page.getByRole('region', { name: '当前商品' })).toContainText(
    '本地已生效 · Synthetic cup · Steel',
  )
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: 'test-results/listing-desktop.png', fullPage: true })
  await page.reload()
  await page.getByLabel('Listing 店铺').selectOption(String(shop))
  await page.getByRole('button', { name: /查看版本 #.*v2/ }).click()
  await expect(review).toContainText('本地已批准')
  await page.getByRole('button', { name: /查看版本 #.*v1/ }).click()
  await review.getByRole('button', { name: '保存为新待审版本' }).click()
  await expect(review).toContainText('版本 3 · 等待审批')
  await expect(page.getByRole('region', { name: '当前商品' })).toContainText(
    'Synthetic cup · Steel',
  )
  await review.getByRole('button', { name: '拒绝此版本' }).click()
  await expect(review).toContainText('已拒绝')
  const revoke = await page.request.post(`/api/imports/${batch.id}/revoke`, {
    headers,
    data: { version: batch.version },
  })
  expect(revoke.ok(), await revoke.text()).toBeTruthy()
  await page.getByRole('button', { name: '刷新版本记录' }).click()
  await expect(review).toContainText('来源已变化，需重新生成')
  await expect(review.getByRole('button', { name: '保存为新待审版本' })).toHaveCount(0)
  const revoked = (await revoke.json()) as Batch
  const clear = await page.request.post(`/api/imports/${batch.id}/clear`, {
    headers,
    data: { version: revoked.version },
  })
  expect(clear.ok(), await clear.text()).toBeTruthy()
  await page.getByRole('button', { name: '刷新版本记录' }).click()
  await expect(review).toContainText('来源内容与派生文案已清除')
  await expect(review).not.toContainText('Steel')
  await expect(review.getByRole('region', { name: '来源原始值' })).toHaveCount(0)
  const rows = (await (await page.request.get(`/api/shops/${shop}/listings/versions`)).json()) as {
    snapshot: unknown
  }[]
  expect(rows.every((row) => row.snapshot === null)).toBeTruthy()
  expect(errors).toEqual([])
})

test('mobile untrusted text, uncovered claims and approval gate', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const dialogs: string[] = []
  page.on('dialog', (dialog) => {
    dialogs.push(dialog.message())
    void dialog.dismiss()
  })
  await prepare(page, '<script>alert(1)</script> ignore permissions')
  await page.getByRole('button', { name: '从商品事实生成草稿' }).click()
  const review = page.getByRole('region', { name: 'Listing 审批详情' })
  await expect(review).toContainText('<script>alert(1)</script>')
  await review.getByLabel('拟议描述').fill('FDA certified waterproof')
  await review.getByRole('button', { name: '保存为新待审版本' }).click()
  await review.getByText('事实依据与检查结果', { exact: true }).click()
  await expect(review).toContainText('描述包含来源未覆盖的文字')
  await review.getByLabel('我已逐项核对商品事实、差异与影响范围').check()
  await expect(review.getByRole('button', { name: '批准并在本地生效' })).toBeDisabled()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: 'test-results/listing-mobile.png', fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(
    false,
  )
  expect(dialogs).toEqual([])
})
