import { expect, test } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'

for (const mobile of [false, true]) {
  const stage = mobile ? 'mobile' : 'desktop'

  test(`model listing consent candidate approval and erase ${stage}`, async ({ page }) => {
    await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1280, height: 800 })
    await page.goto('/listings')
    await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
    await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    const session = await (await page.request.get('/api/auth/session')).json()
    const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
    const created = await page.request.post('/api/shops', {
      headers,
      data: {
        code: `listing-model-e2e-${stage}`,
        name: '合成 Listing 模型店铺',
        platform: 'other',
        market: 'US',
        currency: 'USD',
        timezone: 'Asia/Shanghai',
      },
    })
    expect(created.ok()).toBeTruthy()
    const shop = (await created.json()).id
    const query = new URLSearchParams({
      filename: 'synthetic-listing.csv',
      kind: 'products',
      data_identity: 'synthetic',
      source_channel: 'generic',
      timezone: 'UTC',
    })
    const uploaded = await page.request.post(`/api/shops/${shop}/imports?${query}`, {
      headers: { ...headers, 'Content-Type': 'text/csv' },
      data: 'sku,name,facts\nMODEL-BOTTLE,Synthetic bottle,"容量 500 ml\n仅限冷水\n手洗"\n',
    })
    expect(uploaded.ok()).toBeTruthy()
    const batch = await uploaded.json()
    const preview = await page.request.post(`/api/imports/${batch.id}/preview`, {
      headers,
      data: { version: batch.version, mapping: batch.mapping },
    })
    expect(preview.ok()).toBeTruthy()
    const commit = await page.request.post(`/api/imports/${batch.id}/commit`, {
      headers,
      data: { version: (await preview.json()).version },
    })
    expect(commit.ok()).toBeTruthy()
    await page.goto(`/listings?shop=${shop}`)
    await page.getByRole('button', { name: /MODEL-BOTTLE · Synthetic bottle/ }).click()
    await page.getByRole('link', { name: '生成 AI Listing 候选' }).click()
    await expect(page.getByLabel('执行流程')).toHaveValue('listing_model')
    await expect(page.getByLabel('数据身份')).toHaveValue('synthetic')
    await expect(page.getByLabel('将发送的商品事实')).toContainText('仅限冷水')
    await page.getByLabel('运营目标').fill('将容量放在标题，保留全部使用限制')
    await page.getByText('数据窗口、规则与任务预算', { exact: true }).click()
    await page.getByLabel('模型预算（USD）', { exact: true }).fill('0.03')
    await page.getByLabel(/同意将本次目标文本/).check()
    await page.getByLabel(/我已核对上述商品事实/).check()
    await page.getByLabel('运营目标').fill('标题突出容量，描述先列使用限制')
    await expect(page.getByLabel(/我已核对上述商品事实/)).not.toBeChecked()
    await expect(page.getByRole('button', { name: '启动并运行', exact: true })).toBeDisabled()
    await page.getByLabel(/同意将本次目标文本/).check()
    await page.getByLabel(/我已核对上述商品事实/).check()
    await page.getByRole('button', { name: '启动并运行', exact: true }).click()
    const review = page.getByRole('region', { name: '任务执行详情' })
    const candidate = page.getByRole('region', { name: '模型 Listing 候选预览' })
    await expect(review).toContainText('等待审批')
    await expect(candidate).toContainText('Synthetic bottle · 容量 500 ml')
    await expect(candidate).toContainText('仅限冷水')
    expect(await (await page.request.get(`/api/shops/${shop}/listings/versions`)).json()).toEqual(
      [],
    )
    await candidate.screenshot({
      path: path.join(tmpdir(), `soloops-listing-candidate-${stage}.png`),
    })
    await page.reload()
    await expect(candidate).toContainText('原文覆盖检查通过')
    await review.getByRole('button', { name: '批准当前节点' }).click()
    const link = review.getByRole('link', { name: /到业务页面复查/ })
    await expect(link).toBeVisible()
    const runs = await (await page.request.get(`/api/shops/${shop}/agent/runs`)).json()
    const execution = runs[0].id
    await link.click()
    await expect(page).toHaveURL(/\/listings\?shop=.*listing=/)
    const listing = page.getByRole('region', { name: 'Listing 审批详情' })
    await expect(listing).toContainText('测试替身')
    await expect(listing.getByRole('button', { name: '批准并在本地生效' })).toBeDisabled()
    await listing.getByLabel('我已逐项核对商品事实、差异与影响范围').check()
    await listing.getByRole('button', { name: '批准并在本地生效' }).click()
    await expect(listing).toContainText('本地已批准')
    await page.reload()
    await expect(listing).toContainText('本地已批准')
    await listing.screenshot({ path: path.join(tmpdir(), `soloops-listing-approved-${stage}.png`) })
    const current = await (await page.request.get(`/api/imports/${batch.id}`)).json()
    expect(
      (
        await page.request.post(`/api/imports/${batch.id}/clear`, {
          headers,
          data: { version: current.version },
        })
      ).ok(),
    ).toBeTruthy()
    await page.goto(`/agent?shop=${shop}&execution=${execution}`)
    await expect(review).toContainText('正文已擦除')
    await expect(candidate).toHaveCount(0)
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy()
    expect(errors).toEqual([])
  })
}
