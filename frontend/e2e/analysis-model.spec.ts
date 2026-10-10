import { fillExactTime } from './date-input'
import { expect, test, type Page } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'

async function importCsv(
  page: Page,
  shop: number,
  headers: Record<string, string>,
  kind: string,
  text: string,
): Promise<number> {
  const query = new URLSearchParams({
    filename: 'synthetic-question.csv',
    kind,
    data_identity: 'synthetic',
    source_channel: 'generic',
    timezone: 'UTC',
  })
  const uploaded = await page.request.post(`/api/shops/${shop}/imports?${query}`, {
    headers: { ...headers, 'Content-Type': 'text/csv' },
    data: text,
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
  const committed = await page.request.post(`/api/imports/${draft.id}/commit`, {
    headers,
    data: { version: result.version },
  })
  expect(committed.ok()).toBeTruthy()
  return draft.id
}

for (const mobile of [false, true]) {
  const stage = mobile ? 'mobile' : 'desktop'

  test(`model question evidence approval reload todo and clear ${mobile ? 'mobile' : 'desktop'}`, async ({
    page,
  }) => {
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
        code: `question-e2e-${mobile ? 'mobile' : 'desktop'}`,
        name: '合成经营问数店铺',
        platform: 'other',
        market: 'US',
        currency: 'USD',
        timezone: 'Asia/Shanghai',
      },
    })
    expect(created.ok()).toBeTruthy()
    const shop = ((await created.json()) as { id: number }).id
    await importCsv(
      page,
      shop,
      headers,
      'products',
      'sku,name,unit_cost,cost_currency,facts\nMODEL-001,Synthetic Item,18,USD,Synthetic specification\n',
    )
    const batch = await importCsv(
      page,
      shop,
      headers,
      'orders',
      'order_id,line_id,sku,quantity,unit_price,currency,ordered_at,status,discount,refund\n' +
        'O-MODEL,1,MODEL-001,3,20,USD,2026-10-07 12:00:00,paid,0,0\n',
    )
    await page.goto(`/agent?shop=${shop}&mode=question`)
    await expect(page.getByLabel('执行流程')).toHaveValue('question')
    await expect(page.getByText('模型已配置：synthetic-evidence-model')).toBeVisible()
    await page.getByLabel('数据身份').selectOption('synthetic')
    await page.getByLabel('运营目标').fill('哪些商品销量较高但已知毛利偏低，需要核对哪些数据？')
    await page.getByText('数据窗口、规则与任务预算', { exact: true }).click()
    await fillExactTime(page.getByLabel('订单起始时间（含时区）'), '2026-10-07T00:00:00Z')
    await fillExactTime(page.getByLabel('订单结束时间（不包含）'), '2026-10-08T00:00:00Z')
    await page.getByLabel('模型预算（USD）', { exact: true }).fill('0.03')
    await page.getByLabel(/同意将本次目标文本/).check()
    await page.getByLabel(/同意发送本次范围/).check()
    await page.getByRole('button', { name: '启动并运行', exact: true }).click()
    const review = page.getByRole('region', { name: '任务执行详情' })
    const narrative = page.getByRole('region', { name: '经营问数解释' })
    await expect(review).toContainText('等待审批')
    await expect(narrative).toContainText('SKU MODEL-001')
    await expect(narrative).toContainText('6.0000 USD')
    await expect(narrative).toContainText('不能推断精确净利润')
    await expect(review).toContainText('0.002000')
    const runs = (await (await page.request.get(`/api/shops/${shop}/agent/runs`)).json()) as {
      id: number
    }[]
    const execution = runs[0]!.id
    await narrative.screenshot({
      path: path.join(tmpdir(), `soloops-question-explanation-${stage}.png`),
    })
    await review.getByRole('button', { name: '批准当前节点' }).click()
    await expect(review.getByRole('link', { name: /到业务页面复查/ })).toBeVisible()
    await page.reload()
    await expect(narrative).toContainText('SKU MODEL-001')
    await review.getByRole('link', { name: /到业务页面复查/ }).click()
    await expect(page).toHaveURL(/\/analytics\?shop=.*analysis=/)
    const todo = page.getByRole('region', { name: '分析核对待办' })
    await expect(todo).toContainText('待核对')
    await todo.getByRole('button', { name: '标记核对完成' }).click()
    await expect(todo).toContainText('已核对完成')
    await page.goto(`/agent?shop=${shop}&execution=${execution}`)
    await expect(narrative).toContainText('MODEL-001')
    const detail = (await (await page.request.get(`/api/imports/${batch}`)).json()) as {
      version: number
    }
    expect(
      (
        await page.request.post(`/api/imports/${batch}/clear`, {
          headers,
          data: { version: detail.version },
        })
      ).ok(),
    ).toBeTruthy()
    await page.getByRole('button', { name: '刷新任务' }).click()
    await expect(review).toContainText('正文已擦除')
    await expect(narrative).toHaveCount(0)
    await expect(review).not.toContainText('MODEL-001')
    await page.screenshot({
      path: path.join(tmpdir(), `soloops-question-cleared-${stage}.png`),
      fullPage: true,
    })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy()
    expect(errors).toEqual([])
  })
}
