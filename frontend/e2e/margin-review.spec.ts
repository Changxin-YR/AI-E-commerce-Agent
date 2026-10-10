import { fillExactTime } from './date-input'
import { expect, test } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'
import type { AgentRun } from '../src/types/agent'
import type { ListingVersion, ProductFacts } from '../src/types/listings'

for (const width of [1440, 390]) {
  test(`bounded margin review has separate approvals and two persisted artifacts at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 920 })
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.goto('/agent')
    await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
    await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
    const session = await (await page.request.get('/api/auth/session')).json()
    const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
    async function post<T>(url: string, data: unknown): Promise<T> {
      const response = await page.request.post(url, { headers, data })
      expect(response.ok(), await response.text()).toBeTruthy()
      return (await response.json()) as T
    }
    const shop = await post<{ id: number }>('/api/shops', {
      code: `margin-${width}`,
      name: '合成低毛利复核',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'Asia/Shanghai',
    })
    const base = `/api/shops/${shop.id}`
    async function imported(kind: string, csv: string) {
      const response = await page.request.post(`${base}/imports`, {
        headers,
        params: {
          filename: `margin-${kind}.csv`,
          kind,
          source_channel: 'generic',
          data_identity: 'synthetic',
          timezone: 'UTC',
        },
        data: csv,
      })
      expect(response.ok(), await response.text()).toBeTruthy()
      const batch = await response.json()
      const preview = await post<{ version: number }>(`/api/imports/${batch.id}/preview`, {
        version: batch.version,
        mapping: batch.mapping,
      })
      await post(`/api/imports/${batch.id}/commit`, { version: preview.version })
    }
    await imported(
      'products',
      'sku,name,facts,price,currency,unit_cost,cost_currency\nMARGIN-001,Synthetic Cup,"Material: Steel\nCapacity: 400ml",10,USD,9.5,USD\n',
    )
    await imported(
      'orders',
      'order_id,line_id,sku,quantity,unit_price,currency,ordered_at,status,discount,refund\nMARGIN-O,1,MARGIN-001,2,10,USD,2026-10-07T08:00:00Z,paid,0,0\n',
    )
    const product = (
      (await (await page.request.get(`${base}/listings/products`)).json()) as ProductFacts[]
    )[0]!
    const draft = await post<ListingVersion>(`${base}/listings/generate`, {
      product_id: product.product_id,
      expected_source_row_id: product.source.row_id,
      expected_active_id: null,
    })
    const edited = await post<ListingVersion>(`${base}/listings/versions/${draft.id}/revise`, {
      expected_version: draft.version,
      expected_active_id: null,
      content: { title: 'Synthetic Cup', description: 'Material: Steel' },
    })
    await post(`${base}/listings/versions/${edited.id}/decision`, {
      expected_version: edited.version,
      decision: 'approve',
      facts_confirmed: true,
    })
    await page.goto(`/agent?shop=${shop.id}`)
    await page.getByLabel('执行流程').selectOption('margin_review')
    await page.getByRole('combobox', { name: '数据身份', exact: true }).selectOption('synthetic')
    await page
      .getByRole('combobox', { name: '目标商品', exact: true })
      .selectOption(String(product.product_id))
    await expect(page.getByLabel('复核成本口径')).toHaveValue('seller_history')
    await page.getByText('数据窗口、规则与任务预算', { exact: true }).click()
    await fillExactTime(page.getByLabel('订单结束时间（不包含）', { exact: true }), '')
    await expect(page.getByText(/请填写有效结束时间/)).toBeVisible()
    await fillExactTime(
      page.getByLabel('订单结束时间（不包含）', { exact: true }),
      '2026-10-08T00:00:00+08:00',
    )
    await page.getByRole('button', { name: '启动并运行', exact: true }).click()
    const review = page.getByRole('region', { name: '任务执行详情' })
    const evidence = review.getByRole('region', { name: '低毛利复核依据与建议' })
    await expect(evidence).toContainText('完整毛利排行不可用')
    await expect(evidence).toContainText('补齐数据与成本依据')
    await expect(evidence).toContainText('补回有来源依据的商品参数')
    expect(
      (await evidence.getByRole('heading', { name: '最近7天 · 依据与下一步' }).boundingBox())!
        .width,
    ).toBeGreaterThan(250)
    await evidence.getByText(/核对本地版本/).click()
    await expect(evidence).toContainText('Capacity: 400ml')
    await expect(review).toContainText('当前步骤：保存分析和核对待办')
    await review.getByRole('button', { name: '批准当前节点' }).click()
    await expect(review).toContainText('当前步骤：保存 Listing 模板草稿')
    await expect(review.getByRole('link', { name: /到业务页面复查\s*经营分析/ })).toBeVisible()
    await page.reload()
    await expect(review).toContainText('当前步骤：保存 Listing 模板草稿')
    await review.getByRole('button', { name: '批准当前节点' }).click()
    await expect(review).toContainText('当前步骤：结束')
    await expect(review.getByRole('link', { name: /到业务页面复查/ })).toHaveCount(2)
    await evidence.screenshot({ path: path.join(tmpdir(), `soloops-b1-evidence-${width}.png`) })
    const history = (await (await page.request.get(`${base}/agent/runs`)).json()) as AgentRun[]
    const done = (await (
      await page.request.get(`${base}/agent/runs/${history[0]!.id}`)
    ).json()) as AgentRun
    expect(done.status).toBe('succeeded')
    expect(done.steps_used).toBe(7)
    expect(Date.parse(done.input!.scope.end_at) - Date.parse(done.input!.scope.start_at)).toBe(
      7 * 86400000,
    )
    const writes = done.steps.filter((s) => s.node === 'verify' && s.status === 'completed')
    expect(writes.map((s) => s.output?.record_type)).toEqual(['analysis', 'listing'])
    await review.screenshot({ path: path.join(tmpdir(), `soloops-b1-margin-${width}.png`) })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await review.getByRole('link', { name: /到业务页面复查\s*经营分析/ }).click()
    await expect(page.getByRole('region', { name: '分析核对待办' })).toBeVisible()
    await page.goto(`/agent?shop=${shop.id}&run=${done.id}`)
    await review.getByRole('link', { name: /到业务页面复查\s*Listing 草稿/ }).click()
    await expect(page).toHaveURL(new RegExp(`listing=${writes[1]!.output!.record_id}`))
    const listing = (await (
      await page.request.get(`${base}/listings/versions/${writes[1]!.output!.record_id}`)
    ).json()) as ListingVersion
    expect(listing.status).toBe('draft')
    expect(listing.snapshot?.proposed.description).toBe(product.facts)
    expect(listing.external_status).toBe('not_submitted')
    // The completed task also depends on its old baseline. Visit home first:
    // neither a detail read nor opening the Agent page may be needed to detect it.
    await post(`${base}/listings/versions/${listing.id}/decision`, {
      expected_version: listing.version,
      decision: 'approve',
      facts_confirmed: true,
    })
    await page.goto(`/?shop=${shop.id}&identity=synthetic`)
    const inbox = page.getByRole('region', { name: '统一工作收件箱' })
    await inbox.getByLabel('事项类型').selectOption('agent')
    const update = inbox.getByRole('button', { name: /需要更新数据/ })
    await expect(update).toContainText('1')
    await update.click()
    const task = inbox.locator('li[data-kind="agent"]')
    await expect(task).toHaveCount(1)
    await expect(task).toContainText('需重新检查')
    await inbox.getByRole('button', { name: '刷新收件箱', exact: true }).click()
    await expect(task).toContainText('需重新检查')
    await page.reload()
    await inbox.getByLabel('事项类型').selectOption('agent')
    await expect(inbox.getByRole('button', { name: /需要更新数据/ })).toContainText('1')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect(errors).toEqual([])
  })
}
