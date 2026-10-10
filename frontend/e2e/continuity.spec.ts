import { expect, test, type Page } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'
import type { AgentRun } from '../src/types/agent'
import { fillExactTime } from './date-input'

async function setup(page: Page, width: number, tag: string) {
  await page.setViewportSize({ width, height: 900 })
  await page.goto('/login')
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
    code: `${tag}-${width}`,
    name: 'SYNTHETIC 连续性验收',
    platform: 'other',
    market: 'US',
    currency: 'USD',
    timezone: 'Asia/Shanghai',
  })
  return { shop: shop.id, post, headers }
}

for (const width of [1440, 390]) {
  test(`business native dates and explicit DST choice ${width}`, async ({ page }) => {
    const { shop } = await setup(page, width, 'dates')
    await page.goto(`/analytics?shop=${shop}`)
    await page.getByLabel('显示时区', { exact: true }).fill('America/New_York')
    await page.getByLabel('选择起点日期和时间', { exact: true }).fill('2026-03-08T02:30')
    await expect(page.getByRole('alert')).toContainText('不存在')
    await page.getByLabel('选择起点日期和时间', { exact: true }).fill('2026-11-01T01:30')
    await expect(page.getByRole('alert')).toContainText('出现两次')
    await fillExactTime(
      page.getByLabel('起点（含时区，计入）', { exact: true }),
      '2026-11-01T01:30:00-04:00',
    )
    await page.getByLabel('选择终点日期和时间', { exact: true }).fill('2026-11-01T03:30')
    await expect(page.getByLabel('本次时间范围')).toContainText(
      'America/New_York（计入起点，不计入终点）',
    )
    await expect(page.getByRole('alert')).toHaveCount(0)
    await page.getByRole('button', { name: '最近 7 天', exact: true }).click()
    const start = await page.getByLabel('起点（含时区，计入）', { exact: true }).inputValue()
    const end = await page.getByLabel('终点（含时区，不计入）', { exact: true }).inputValue()
    expect(Date.parse(end) - Date.parse(start)).toBe(7 * 86400000)
    await page.getByRole('button', { name: '最近 30 天', exact: true }).click()
    expect(
      Date.parse(await page.getByLabel('终点（含时区，不计入）', { exact: true }).inputValue()) -
        Date.parse(await page.getByLabel('起点（含时区，计入）', { exact: true }).inputValue()),
    ).toBe(30 * 86400000)
    await page.screenshot({
      path: path.join(tmpdir(), `soloops-r2-dates-${width}.png`),
      fullPage: true,
    })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })

  test(`agent and support saved deep links, history and unsaved edits ${width}`, async ({
    page,
  }) => {
    const { shop, post, headers } = await setup(page, width, 'continuity')
    const other = await post<{ id: number }>('/api/shops', {
      code: `continuity-other-${width}`,
      name: 'SYNTHETIC 第二店铺',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'UTC',
    })
    const base = `/api/shops/${shop}`
    const upload = await page.request.post(`${base}/imports`, {
      headers,
      params: {
        filename: 'synthetic-messages.csv',
        kind: 'messages',
        source_channel: 'shopify',
        data_identity: 'synthetic',
        timezone: 'UTC',
      },
      data: 'message_id,body,language,sent_at\nCONT-M1,Where is my order?,en,2026-10-09T08:00:00Z\nCONT-M2,Please refund my order.,en,2026-10-09T09:00:00Z\n',
    })
    expect(upload.ok(), await upload.text()).toBeTruthy()
    const batch = await upload.json()
    const preview = await post<{ version: number }>(`/api/imports/${batch.id}/preview`, {
      version: batch.version,
      mapping: batch.mapping,
    })
    await post(`/api/imports/${batch.id}/commit`, { version: preview.version })
    const messages = (await (await page.request.get(`${base}/support/messages`)).json()) as {
      id: number
      message_id: string
    }[]
    const message = messages.find((m) => m.message_id === 'CONT-M1')!
    const input = {
      request_id: crypto.randomUUID(),
      template: 'support',
      goal: '',
      product_id: null,
      message_id: message.id,
      allow_model: false,
      budget: { max_steps: 12, max_seconds: 120, max_cost_usd: '0' },
      scope: {
        start_at: '2026-10-01T00:00:00Z',
        end_at: '2026-10-10T00:00:00Z',
        timezone: 'Asia/Shanghai',
        currency: 'USD',
        data_identity: 'synthetic',
        channel: 'shopify',
        intent: 'low_margin',
        min_quantity: 1,
        max_margin_percent: '20',
        max_age_hours: 24,
      },
    }
    const run = await post<AgentRun>(`${base}/agent/runs`, input)
    const paused = await post<AgentRun>(`${base}/agent/runs/${run.id}`, {
      version: run.version,
      action: 'pause',
    })
    await page.goto(`/agent?shop=${shop}&execution=${run.id}`)
    const review = page.getByRole('region', { name: '任务执行详情' })
    await expect(review).toContainText('已暂停')
    await expect(page.getByRole('combobox', { name: '数据身份', exact: true })).toHaveValue(
      'synthetic',
    )
    await expect(page.getByRole('combobox', { name: '检查渠道', exact: true })).toHaveValue(
      'shopify',
    )
    await expect(page.getByRole('combobox', { name: '目标消息', exact: true })).toHaveValue(
      String(message.id),
    )
    await page.reload()
    await expect(review).toContainText('已暂停')
    const after = (await (
      await page.request.get(`${base}/agent/runs/${run.id}`)
    ).json()) as AgentRun
    expect(after.version).toBe(paused.version)
    expect(after.steps).toEqual(paused.steps)
    expect(after.steps_used).toBe(0)
    expect(await (await page.request.get(`${base}/agent/runs`)).json()).toHaveLength(1)
    await review.getByRole('button', { name: '确认预算并恢复' }).click()
    await expect(review).toContainText('等待审批')
    await page.getByLabel('任务店铺').selectOption(String(other.id))
    await expect(review).toHaveCount(0)
    await expect(page.getByLabel('任务店铺')).toBeEnabled()
    await page.goBack()
    await expect(review).toContainText('等待审批')
    await page.goForward()
    await expect(page.getByLabel('任务店铺')).toHaveValue(String(other.id))
    await expect(page.getByLabel('任务店铺')).toBeEnabled()
    await page.goBack()
    await expect(page.getByRole('combobox', { name: '目标消息', exact: true })).toHaveValue(
      String(message.id),
    )
    await review.getByRole('button', { name: '批准当前节点' }).click()
    await expect(review).toContainText('已完成')
    await review.getByRole('link', { name: /到业务页面复查/ }).click()
    const draft = page.getByRole('region', { name: '客服草稿详情' })
    await expect(draft).toBeVisible()
    const firstUrl = page.url()
    await draft.getByLabel('回复正文（仅草稿）').fill('SYNTHETIC saved reply; no delivery.')
    await page.getByRole('button', { name: '展开全部功能', exact: true }).click()
    await page.getByRole('link', { name: '经营分析', exact: true }).click()
    await expect(page).toHaveURL(firstUrl)
    await expect(page.getByRole('alert')).toContainText('尚未保存')
    await draft.getByRole('button', { name: '保存修改', exact: true }).click()
    await page.reload()
    await expect(draft.getByLabel('回复正文（仅草稿）')).toHaveValue(
      'SYNTHETIC saved reply; no delivery.',
    )
    await page.getByRole('button', { name: /CONT-M2 ·/ }).click()
    await page.getByRole('button', { name: '生成本地回复草稿' }).click()
    await expect(page).toHaveURL(/draft=/)
    await expect(
      page.getByText('草稿与接管摘要已保存，请核对全部诉求和证据。', { exact: true }),
    ).toBeVisible()
    const secondUrl = page.url()
    expect(secondUrl).not.toBe(firstUrl)
    await page.reload()
    await expect(draft).toContainText('退款 / 退货')
    await page.goBack()
    await expect(page.getByRole('region', { name: '消息证据核验' })).toContainText('CONT-M2')
    await expect(page.getByLabel('客服店铺')).toBeEnabled()
    await page.goBack()
    await expect(draft.getByLabel('回复正文（仅草稿）')).toHaveValue(
      'SYNTHETIC saved reply; no delivery.',
    )
    await page.goForward()
    await expect(page.getByRole('region', { name: '消息证据核验' })).toContainText('CONT-M2')
    await expect(page.getByLabel('客服店铺')).toBeEnabled()
    await page.goForward()
    await expect(page).toHaveURL(secondUrl)
    await expect(draft).toContainText('外部未提交')
    await page.screenshot({
      path: path.join(tmpdir(), `soloops-r2-continuity-${width}.png`),
      fullPage: true,
    })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    const draftId = new URL(secondUrl).searchParams.get('draft')!
    await page.goto(`/support?shop=${other.id}&draft=${draftId}`)
    await expect(page.getByRole('alert')).toContainText('无权访问')
    await expect(draft).toHaveCount(0)
    await page.goto(secondUrl)
    const currentBatch = await (await page.request.get(`/api/imports/${batch.id}`)).json()
    const revoked = await post<{ version: number }>(`/api/imports/${batch.id}/revoke`, {
      version: currentBatch.version,
    })
    await page.reload()
    await expect(draft).toContainText('依据已失效')
    await post(`/api/imports/${batch.id}/clear`, { version: revoked.version })
    await page.reload()
    await expect(draft).toContainText('正文和证据快照已擦除')
    await page.goto(`/agent?shop=${other.id}&execution=${run.id}`)
    await expect(page.getByRole('alert')).toContainText('无权访问')
    await expect(review).toHaveCount(0)
  })
}
