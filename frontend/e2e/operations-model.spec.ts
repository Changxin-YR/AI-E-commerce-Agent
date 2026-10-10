import { fillExactTime } from './date-input'
import { expect, test, type Page } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'

async function importOrders(
  page: Page,
  shop: number,
  headers: Record<string, string>,
): Promise<number> {
  const query = new URLSearchParams({
    filename: 'synthetic-operations-model.csv',
    kind: 'orders',
    data_identity: 'synthetic',
    source_channel: 'generic',
    timezone: 'UTC',
  })
  const uploaded = await page.request.post(`/api/shops/${shop}/imports?${query}`, {
    headers: { ...headers, 'Content-Type': 'text/csv' },
    data:
      'order_id,line_id,sku,quantity,unit_price,currency,ordered_at,status,discount,refund,fulfillment_status\n' +
      'SYNTHETIC-OPS,1,OPS-SKU,2,20,USD,2026-10-07T12:00:00Z,paid,0,0,unfulfilled\n',
  })
  expect(uploaded.ok()).toBeTruthy()
  const draft = (await uploaded.json()) as {
    id: number
    version: number
    mapping: Record<string, string>
  }
  const preview = await page.request.post(`/api/imports/${draft.id}/preview`, {
    headers,
    data: { version: draft.version, mapping: draft.mapping },
  })
  expect(preview.ok()).toBeTruthy()
  const result = (await preview.json()) as { version: number }
  const commit = await page.request.post(`/api/imports/${draft.id}/commit`, {
    headers,
    data: { version: result.version },
  })
  expect(commit.ok()).toBeTruthy()
  return draft.id
}

for (const mobile of [false, true]) {
  const stage = mobile ? 'mobile' : 'desktop'

  test(`operations model overview approval task reload and clear ${stage}`, async ({ page }) => {
    await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1280, height: 800 })
    await page.goto('/agent')
    await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
    await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    const session = (await (await page.request.get('/api/auth/session')).json()) as {
      csrf_token: string
    }
    const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
    const created = await page.request.post('/api/shops', {
      headers,
      data: {
        code: `operations-model-e2e-${stage}`,
        name: '合成运营模型店铺',
        platform: 'other',
        market: 'US',
        currency: 'USD',
        timezone: 'Asia/Shanghai',
      },
    })
    expect(created.ok()).toBeTruthy()
    const shop = ((await created.json()) as { id: number }).id
    const batch = await importOrders(page, shop, headers)
    await page.goto(`/agent?shop=${shop}&mode=daily_model`)
    await expect(page.getByLabel('执行流程')).toHaveValue('daily_model')
    await page.getByLabel('数据身份').selectOption('synthetic')
    await page.getByLabel('运营目标').fill('检查导入数据并列出需要核对的事项。')
    await page.getByText('数据窗口、规则与任务预算', { exact: true }).click()
    await fillExactTime(page.getByLabel('订单起始时间（含时区）'), '2026-10-07T00:00:00Z')
    await fillExactTime(page.getByLabel('订单结束时间（不包含）'), '2026-10-08T00:00:00Z')
    await page.getByLabel('模型预算（USD）', { exact: true }).fill('0.03')
    const consent = page.getByLabel(/我已核对运营范围/)
    await expect(consent).toBeEnabled()
    await page.getByLabel(/同意将本次目标文本/).check()
    await consent.check()
    // A fresh preview invalidates both consent checkboxes even if the result is identical.
    await page.getByRole('button', { name: '刷新运营数据' }).click()
    await expect(consent).not.toBeChecked()
    await expect(consent).toBeEnabled()
    await page.getByLabel(/同意将本次目标文本/).check()
    await consent.check()
    await page.getByRole('button', { name: '启动并运行', exact: true }).click()
    const review = page.getByRole('region', { name: '任务执行详情' })
    const narrative = page.getByRole('region', { name: '运营检查解释' })
    await expect(review).toContainText('等待审批')
    await expect(narrative).toContainText('实时物流 · 未检查')
    await expect(narrative).toContainText('已知商品毛利不是净利润')
    await expect(narrative).toContainText('数据不足')
    await expect(narrative.locator('article')).toHaveCount(9)
    await expect(review).toContainText('0.001000')
    const runs = (await (await page.request.get(`/api/shops/${shop}/agent/runs`)).json()) as {
      id: number
    }[]
    const execution = runs[0]!.id
    await narrative.evaluate((element) => element.scrollIntoView({ block: 'start' }))
    await expect(page.locator('.skip-link')).not.toBeInViewport()
    await page.screenshot({
      path: path.join(tmpdir(), `soloops-operations-model-${stage}.png`),
    })
    await page.reload()
    await expect(narrative).toContainText('实时物流 · 未检查')
    await review.getByRole('button', { name: '批准当前节点' }).click()
    await expect(review.getByRole('link', { name: /到业务页面复查/ })).toBeVisible()
    await review.getByRole('link', { name: /到业务页面复查/ }).click()
    await expect(page).toHaveURL(/\/?\?shop=.*run=/)
    await page.locator('.task-row').filter({ hasText: 'SYNTHETIC-OPS' }).click()
    const detail = page.getByRole('region', { name: '待办审批详情' })
    await detail.getByRole('button', { name: '批准并创建待办' }).click()
    await detail.getByRole('button', { name: '标记完成' }).click()
    await expect(detail).toContainText('已完成')
    await page.goto(`/agent?shop=${shop}&execution=${execution}`)
    await expect(narrative).toContainText('实时物流 · 未检查')
    const imported = (await (await page.request.get(`/api/imports/${batch}`)).json()) as {
      version: number
    }
    expect(
      (
        await page.request.post(`/api/imports/${batch}/clear`, {
          headers,
          data: { version: imported.version },
        })
      ).ok(),
    ).toBeTruthy()
    await page.getByRole('button', { name: '刷新任务' }).click()
    await expect(review).toContainText('正文已擦除')
    await expect(narrative).toHaveCount(0)
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      JSON.stringify(
        await page.locator('main *').evaluateAll((elements) =>
          elements
            .filter((el) => el.getBoundingClientRect().right > innerWidth)
            .slice(0, 12)
            .map((el) => ({
              tag: el.tagName,
              class: el.className,
              width: el.getBoundingClientRect().width,
              text: el.textContent?.slice(0, 80),
            })),
        ),
      ),
    ).toBeTruthy()
    expect(errors).toEqual([])
  })
}
