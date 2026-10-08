import { expect, test, type Page } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'

const scope = {
  start_at: '2026-10-07T00:00:00Z',
  end_at: '2026-10-10T00:00:00Z',
  timezone: 'Asia/Shanghai',
  currency: 'USD',
  data_identity: 'synthetic',
}
async function prepare(page: Page) {
  await page.goto('/')
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
  const session = (await (await page.request.get('/api/auth/session')).json()) as {
    csrf_token: string
  }
  const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
  async function post<T>(url: string, data: unknown): Promise<T> {
    const response = await page.request.post(url, { headers, data })
    expect(response.ok(), await response.text()).toBeTruthy()
    return (await response.json()) as T
  }
  const shop = await post<{ id: number }>('/api/shops', {
    code: `inbox-${test.info().testId.slice(-16)}`,
    name: '合成收件箱店铺',
    platform: 'other',
    market: 'US',
    currency: 'USD',
    timezone: 'Asia/Shanghai',
  })
  async function imported(kind: string, csv: string) {
    const uploaded = await page.request.post(`/api/shops/${shop.id}/imports`, {
      headers,
      params: {
        filename: `inbox-${kind}.csv`,
        kind,
        source_channel: 'generic',
        data_identity: 'synthetic',
        timezone: 'UTC',
      },
      data: csv,
    })
    expect(uploaded.ok(), await uploaded.text()).toBeTruthy()
    const batch = (await uploaded.json()) as {
      id: number
      version: number
      mapping: Record<string, string>
    }
    const preview = await post<{ version: number }>(`/api/imports/${batch.id}/preview`, {
      version: batch.version,
      mapping: batch.mapping,
    })
    return post<{ id: number; version: number }>(`/api/imports/${batch.id}/commit`, {
      version: preview.version,
    })
  }
  await imported('products', 'sku,name,facts\nINBOX-001,Synthetic cup,Steel\n')
  await imported(
    'messages',
    'message_id,sent_at,body,language,order_id\nINBOX-M,2026-10-08T01:00:00Z,Where is my order?,en,\n',
  )
  const base = `/api/shops/${shop.id}`
  const product = (
    (await (await page.request.get(`${base}/listings/products`)).json()) as {
      product_id: number
      source: { row_id: number }
    }[]
  )[0]!
  const listing = await post<{ id: number }>(`${base}/listings/generate`, {
    product_id: product.product_id,
    expected_source_row_id: product.source.row_id,
    expected_active_id: null,
  })
  const message = (
    (await (await page.request.get(`${base}/support/messages`)).json()) as {
      id: number
      source: { row_id: number }
    }[]
  )[0]!
  const reply = await post<{ id: number }>(`${base}/support/messages/${message.id}/generate`, {
    expected_source_row_id: message.source.row_id,
  })
  const run = await post<{ id: number }>(`${base}/operations/runs`, {
    request_id: crypto.randomUUID(),
    scope,
  })
  const started = await post<{ id: number; version: number }>(`${base}/agent/runs`, {
    request_id: crypto.randomUUID(),
    scope,
  })
  const agent = await post<{ id: number; version: number }>(`${base}/agent/runs/${started.id}`, {
    action: 'advance',
    version: started.version,
  })
  const grant = await post<{ id: number }>(`${base}/authorizations`, {
    request_id: crypto.randomUUID(),
    execution_id: agent.id,
    expected_version: agent.version,
    max_uses: 1,
    valid_hours: 1,
    confirmed: true,
  })
  const revision = (await (await page.request.get(`${base}/analytics/revision`)).json()) as number
  const analysis = await post<{ id: number }>(`${base}/analytics/saved`, {
    scope,
    expected_revision: revision,
  })
  await post(`${base}/analytics/saved/${analysis.id}/todo`, {})
  const overviewScope = {
    shop_ids: [shop.id],
    start_date: '2026-10-07',
    end_date: '2026-10-09',
    timezone: 'Asia/Shanghai',
    data_identity: 'synthetic',
  }
  const overview = await post<{ id: number }>('/api/overview/reports', {
    request_id: crypto.randomUUID(),
    scope: overviewScope,
    expected_revisions: { [shop.id]: revision },
  })
  return { shop: shop.id, listing, reply, run, agent, grant, analysis, overview }
}

test('unified workbench opens exact cross-module records and original approvals', async ({
  page,
}) => {
  const records = await prepare(page)
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text())
  })
  const inbox = page.getByRole('region', { name: '统一工作收件箱' })
  async function home() {
    await page.goto('/')
    await inbox.getByLabel('查看店铺').selectOption(String(records.shop))
    await expect(inbox.getByRole('list', { name: '工作事项' })).toBeVisible()
  }
  async function open(kind: string) {
    await home()
    await inbox.locator(`li[data-kind="${kind}"]`).getByRole('link').click()
  }
  await home()
  await expect(inbox).toContainText('最近实际运行')
  await expect(inbox.locator('[data-kind="operation_task"]')).toHaveCount(1)
  await page.screenshot({ path: path.join(tmpdir(), 'soloops-workbench-first-desktop.png') })
  await inbox.screenshot({ path: path.join(tmpdir(), 'soloops-workbench-desktop.png') })
  await open('listing')
  await expect(page.getByLabel('Listing 店铺')).toHaveValue(String(records.shop))
  const listing = page.getByRole('region', { name: 'Listing 审批详情' })
  await expect(listing).toContainText('Synthetic cup')
  await listing.getByLabel('我已逐项核对商品事实、差异与影响范围').check()
  await listing.getByRole('button', { name: '批准并在本地生效' }).click()
  await expect(listing).toContainText('本地生效')
  await open('reply')
  const reply = page.getByRole('region', { name: '客服草稿详情' })
  await expect(reply).toContainText(`回复草稿 #${records.reply.id}`)
  await expect(page.getByLabel('客服店铺')).toHaveValue(String(records.shop))
  await open('analysis_todo')
  await expect(page).toHaveURL(new RegExp(`analysis=${records.analysis.id}`))
  await expect(page.getByRole('heading', { name: '订单行与来源' })).toBeVisible()
  await page.getByRole('button', { name: '标记核对完成' }).click()
  await expect(page.getByRole('region', { name: '分析核对待办' })).toContainText('已核对完成')
  await page.reload()
  await expect(page.getByRole('region', { name: '分析核对待办' })).toContainText('已核对完成')
  await page.getByRole('button', { name: '重新打开核对待办' }).click()
  await expect(page.getByRole('region', { name: '分析核对待办' })).toContainText('待核对')
  await open('overview')
  await expect(page.getByRole('region', { name: '经营总览结果' })).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`report=${records.overview.id}`))
  await open('agent')
  await expect(page.getByRole('region', { name: '任务执行详情' })).toContainText(
    `任务 #${records.agent.id}`,
  )
  await expect(page.getByRole('region', { name: '任务执行详情' })).toContainText('等待审批')
  await open('authorization')
  const grant = page.locator(`#authorization-${records.grant.id}`)
  await expect(grant).toHaveAttribute('open', '')
  await expect(grant).toContainText('已用 0 / 1')
  await open('operation_task')
  const task = page.getByRole('region', { name: '待办审批详情' })
  await expect(task).toContainText('INBOX-M')
  await expect(page.getByLabel('所属店铺')).toHaveValue(String(records.shop))
  await open('operation_run')
  await expect(page).toHaveURL(new RegExp(`run=${records.run.id}`))
  await home()
  await inbox.getByLabel('筛选身份').selectOption('user_import')
  await expect(inbox).toContainText('当前范围还没有工作记录')
  expect(errors).toEqual([])
})

test('mobile inbox scope, direct link reload and inaccessible shop handling', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const records = await prepare(page)
  await page.goto('/')
  const inbox = page.getByRole('region', { name: '统一工作收件箱' })
  await inbox.getByLabel('查看店铺').selectOption(String(records.shop))
  await inbox.getByLabel('事项类型').selectOption('listing')
  await expect(inbox.locator('li[data-kind="listing"]')).toBeVisible()
  await page.screenshot({ path: path.join(tmpdir(), 'soloops-workbench-first-mobile.png') })
  await inbox.screenshot({ path: path.join(tmpdir(), 'soloops-workbench-mobile.png') })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await inbox.locator('li[data-kind="listing"]').getByRole('link').click()
  await expect(page).toHaveURL(new RegExp(`listing=${records.listing.id}`))
  await page.reload()
  await expect(page.getByRole('region', { name: 'Listing 审批详情' })).toContainText(
    'Synthetic cup',
  )
  await page.goto(`/listings?shop=999999&listing=${records.listing.id}`)
  await expect(page.getByRole('alert')).toContainText('店铺不存在或无权访问')
  await expect(page.getByRole('region', { name: 'Listing 审批详情' })).toHaveCount(0)
  await page.goto(`/?shop=${records.shop}&run=invalid`)
  await expect(page.getByRole('alert')).toContainText('记录链接无效')
  await expect(page.getByRole('complementary', { name: '最近检查摘要' })).toHaveCount(0)
})
