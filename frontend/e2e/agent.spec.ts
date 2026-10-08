import { expect, test, type Page } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'

async function setup(page: Page): Promise<{ shop: number; headers: Record<string, string> }> {
  await page.goto('/agent')
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
  const session = (await (await page.request.get('/api/auth/session')).json()) as {
    csrf_token: string
  }
  const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
  const created = await page.request.post('/api/shops', {
    headers,
    data: {
      code: `agent-${test.info().testId.slice(-16)}`,
      name: '合成 Agent 店铺',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'Asia/Shanghai',
    },
  })
  expect(created.ok()).toBeTruthy()
  const shop = ((await created.json()) as { id: number }).id
  await page.goto('/agent')
  await page.getByLabel('任务店铺').selectOption(String(shop))
  await page.getByLabel('数据身份').selectOption('synthetic')
  return { shop, headers }
}

async function inventory(
  page: Page,
  shop: number,
  headers: Record<string, string>,
): Promise<number> {
  const query = new URLSearchParams({
    filename: 'agent-synthetic.csv',
    kind: 'inventory',
    data_identity: 'synthetic',
    source_channel: 'generic',
    timezone: 'UTC',
  })
  const uploaded = await page.request.post(`/api/shops/${shop}/imports?${query}`, {
    headers: { ...headers, 'Content-Type': 'text/csv' },
    data: `sku,available,snapshot_at,safety_threshold\nAGENT-001,2,${new Date(Date.now() - 3600000).toISOString()},5\n`,
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
  const version = ((await preview.json()) as { version: number }).version
  const committed = await page.request.post(`/api/imports/${draft.id}/commit`, {
    headers,
    data: { version },
  })
  expect(committed.ok()).toBeTruthy()
  return draft.id
}

test('agent evidence approval budget resume verification replay and erasure', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const { shop, headers } = await setup(page)
  const batch = await inventory(page, shop, headers)
  await page.getByText('数据窗口、规则与任务预算', { exact: true }).click()
  await page.getByLabel('执行步数上限', { exact: true }).fill('1')
  await page.getByRole('button', { name: '启动并运行', exact: true }).click()
  const review = page.getByRole('region', { name: '任务执行详情' })
  await expect(review).toContainText('等待审批')
  await expect(review).toContainText('AGENT-001')
  await review.getByText('查看 1 条事实来源', { exact: true }).click()
  await review.getByText(/来源：agent-synthetic.csv/).click()
  await review.getByRole('button', { name: '查看来源原始行' }).click()
  await expect(review.getByRole('region', { name: '来源原始值' })).toContainText('AGENT-001')
  await review.getByRole('button', { name: '批准当前节点' }).click()
  await expect(review).toContainText('已达到执行步数上限')
  await review.getByLabel('恢复后总步数上限').fill('4')
  await review.getByRole('button', { name: '确认预算并恢复' }).click()
  await expect(review).toContainText('已完成')
  await expect(review.getByRole('link', { name: /到业务页面复查/ })).toBeVisible()
  await expect(review).toContainText('propose_tasks v1')
  await page.screenshot({ path: path.join(tmpdir(), 'soloops-agent-desktop.png'), fullPage: true })
  const taskPage = (await (
    await page.request.get(`/api/shops/${shop}/operations/tasks?data_identity=synthetic`)
  ).json()) as { items: { status: string }[] }
  expect(taskPage.items).toHaveLength(1)
  expect(taskPage.items[0]?.status).toBe('pending_approval')
  await page.reload()
  await page.getByLabel('任务店铺').selectOption(String(shop))
  await expect(review).toContainText('已完成')
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
  await expect(review).toContainText('任务内容和步骤正文已擦除')
  await expect(review).not.toContainText('AGENT-001')
  expect(errors).toEqual([])
})

test('mobile empty checks and unconfigured model show real states', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await setup(page)
  await page.getByRole('button', { name: '启动并运行', exact: true }).click()
  const review = page.getByRole('region', { name: '任务执行详情' })
  await expect(review).toContainText('本次检查未产生异常候选')
  await page.getByLabel('执行流程').selectOption('natural')
  await page.getByLabel('运营目标').fill('检查今日运营')
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: '启动并运行', exact: true }).click()
  await expect(review).toContainText('等待模型配置')
  await review.getByRole('button', { name: '取消任务' }).click()
  await expect(review).toContainText('已取消')
  await page.screenshot({ path: path.join(tmpdir(), 'soloops-agent-mobile.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})
