/* global console, process */
import { randomUUID } from 'node:crypto'
import { expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import {
  output,
  serial,
  restart,
  login,
  navigate,
  shot,
  call,
  seedImport,
  createShop,
} from './android-device.mjs'

// A4 device acceptance: approval reject/cancel, pause and resume, recovery after
// an app restart, and the unsaved-record protection on the operations inbox.
const results = []
const record = (check, evidence = {}) => {
  results.push({ check, passed: true, ...evidence })
  console.log(check)
}
let active
await mkdir(output, { recursive: true })

async function runStatus(page, shop, id) {
  const run = await call(page, `/shops/${shop}/agent/runs/${id}`)
  expect(run.status, JSON.stringify(run.body)).toBeLessThan(300)
  return run.body
}

async function waitStatus(page, shop, id, expected, timeout = 60000) {
  const deadline = Date.now() + timeout
  let status = ''
  while (Date.now() < deadline) {
    status = (await runStatus(page, shop, id)).status
    if (status === expected) return status
    await page.waitForTimeout(1000)
  }
  throw new Error(`run ${id} stayed ${status}, expected ${expected}`)
}

// Start a local Listing template run through the device UI; it stops at the
// draft approval node, which is where reject/cancel are offered.
async function listingRun(page, shop) {
  await navigate(page, '/agent')
  await page.getByLabel('任务店铺').selectOption(String(shop))
  await page.getByLabel('数据身份').selectOption('synthetic')
  await page.waitForTimeout(1000)
  await page.getByLabel('执行流程').selectOption('listing')
  await page.getByLabel('查找商品或消息').fill('LIFE-001')
  await page.getByLabel('查找商品或消息').blur()
  await expect(
    page.getByLabel('目标商品').locator('option', { hasText: 'LIFE-001' }),
  ).toHaveCount(1)
  await page.getByLabel('目标商品').selectOption({ label: 'LIFE-001 · 安卓合成任务商品' })
  await expect(page.getByLabel('执行流程')).toHaveValue('listing')
  const start = page.getByRole('button', { name: '启动并运行', exact: true })
  await expect(start).toBeEnabled({ timeout: 60000 })
  await start.click()
  const review = page.getByRole('region', { name: '任务执行详情' })
  await expect(review).toContainText('等待审批', { timeout: 90000 })
  return review
}

try {
  active = await restart()
  let { page } = active
  await login(page)

  const stamp = Date.now()
  const shop = await createShop(
    page,
    `lifecycle-e2e-android-${stamp}`,
    `安卓合成任务 ${stamp}`,
  )
  const batch = await seedImport(
    page,
    shop,
    'a4-lifecycle.csv',
    'products',
    'sku,name,facts\nLIFE-001,安卓合成任务商品,容量 300 ml\n',
  )

  // 拒绝：a waiting candidate is rejected and stays rejected.
  const rejectReview = await listingRun(page, shop)
  const rejectRun = (await call(page, `/shops/${shop}/agent/runs`)).body[0]
  await rejectReview.getByRole('button', { name: '拒绝当前节点' }).click()
  await waitStatus(page, shop, rejectRun.id, 'rejected')
  await shot('a4-agent-rejected')
  record('agent-approval-rejected', { shop, run: rejectRun.id, status: 'rejected' })

  // 取消：a waiting candidate is cancelled and keeps its history.
  const cancelReview = await listingRun(page, shop)
  const cancelRun = (await call(page, `/shops/${shop}/agent/runs`)).body[0]
  await cancelReview.getByRole('button', { name: '取消任务' }).click()
  await waitStatus(page, shop, cancelRun.id, 'cancelled')
  const cancelled = await runStatus(page, shop, cancelRun.id)
  expect(cancelled.steps.length).toBeGreaterThan(0)
  await shot('a4-agent-cancelled')
  record('agent-task-cancelled', {
    shop,
    run: cancelRun.id,
    status: cancelled.status,
    steps: cancelled.steps.length,
  })

  // 暂停/恢复：a server-side run left at `ready` is paused and then resumed by UI.
  const end = new Date()
  const start = new Date(end.getTime() - 7 * 86400000)
  const product = (await call(page, `/shops/${shop}/listings/products?q=LIFE-001&offset=0`)).body[0]
  const created = await call(page, `/shops/${shop}/agent/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      request_id: randomUUID(),
      template: 'listing',
      product_id: product.product_id,
      goal: '',
      budget: { max_steps: 12, max_seconds: 120, max_cost_usd: '0.03' },
      scope: {
        cost_mode: 'current_estimate',
        start_at: start.toISOString(),
        end_at: end.toISOString(),
        timezone: 'Asia/Shanghai',
        currency: 'USD',
        data_identity: 'synthetic',
        channel: 'generic',
        intent: 'low_margin',
        min_quantity: 1,
        max_margin_percent: 20,
        rule_revision_id: 0,
        max_age_hours: 24,
      },
    }),
  })
  expect(created.status, JSON.stringify(created.body)).toBeLessThan(300)
  expect(created.body.status).toBe('ready')
  const pausedRunId = created.body.id
  await navigate(page, '/agent')
  await page.getByLabel('任务店铺').selectOption(String(shop))
  await page.getByRole('button', { name: '刷新任务' }).click()
  await page.locator('.button-row button', { hasText: `#${pausedRunId} ·` }).first().click()
  const pausedReview = page.getByRole('region', { name: '任务执行详情' })
  await expect(pausedReview).toBeVisible({ timeout: 60000 })
  await pausedReview.getByRole('button', { name: '暂停任务' }).click()
  await waitStatus(page, shop, pausedRunId, 'paused')
  const resume = pausedReview.getByRole('button', { name: '确认预算并恢复' })
  await expect(resume).toBeVisible({ timeout: 60000 })
  await shot('a4-agent-paused')
  await resume.click()
  await waitStatus(page, shop, pausedRunId, 'waiting_approval', 90000)
  await expect(pausedReview).toContainText('等待审批', { timeout: 60000 })
  record('agent-pause-and-resume', { shop, run: pausedRunId, resumed: 'waiting_approval' })

  // 任务恢复：after a force-stop the same run is recovered and can be approved.
  active = await restart()
  page = active.page
  await login(page)
  await navigate(page, '/agent')
  await page.getByLabel('任务店铺').selectOption(String(shop))
  await page.getByRole('button', { name: '刷新任务' }).click()
  await page.locator('.button-row button', { hasText: `#${pausedRunId} ·` }).first().click()
  const recovered = page.getByRole('region', { name: '任务执行详情' })
  await expect(recovered).toContainText('步骤与操作记录', { timeout: 60000 })
  await expect(recovered.getByRole('button', { name: '批准当前节点' })).toBeVisible({
    timeout: 60000,
  })
  await recovered.getByRole('button', { name: '批准当前节点' }).click()
  await waitStatus(page, shop, pausedRunId, 'succeeded', 90000)
  await shot('a4-agent-recovered')
  record('task-recovery-after-restart', {
    shop,
    run: pausedRunId,
    status: 'succeeded',
  })

  // 任务侧业务保护：an unsaved operations note blocks running and switching.
  const snapshot = new Date(Date.now() - 3600000).toISOString()
  await seedImport(
    page,
    shop,
    'a4-lifecycle-stock.csv',
    'inventory',
    `sku,available,snapshot_at,safety_threshold\nLIFE-001,2,${snapshot},5\n`,
    true,
  )
  await navigate(page, '/')
  await page.locator('#ops-shop').selectOption(String(shop))
  await page.locator('#ops-identity').selectOption('synthetic')
  await page.locator('#ops-channel').selectOption('generic')
  await page.getByRole('button', { name: '运行今日运营' }).click()
  await expect(page.getByRole('region', { name: '巡检结果' })).toContainText('新增候选', {
    timeout: 90000,
  })
  await page.locator('.task-row').first().click()
  const detail = page.getByRole('region', { name: '待办审批详情' })
  await detail.getByLabel('处理备注').fill('未保存的核查记录')
  await expect(page.getByText('有未保存的处理记录，请先保存后切换或刷新。')).toBeVisible({
    timeout: 30000,
  })
  await expect(page.getByRole('button', { name: '运行今日运营' })).toBeDisabled()
  await shot('a4-operations-dirty-protection')
  await detail.getByRole('button', { name: '批准并创建待办' }).click()
  await expect(detail.getByRole('heading', { name: /事项 #.*待处理/ })).toBeVisible({
    timeout: 60000,
  })
  await expect(page.getByText('有未保存的处理记录，请先保存后切换或刷新。')).toHaveCount(0)
  const tasks = await call(
    page,
    `/shops/${shop}/operations/tasks?data_identity=synthetic&channel=generic&offset=0`,
  )
  record('operations-dirty-note-protection', {
    shop,
    batch,
    tasks: tasks.body.items.length,
    note: tasks.body.items[0]?.note ?? null,
  })
} catch (error) {
  results.push({ check: 'failure', passed: false, message: String(error) })
  if (active?.page) {
    console.log(await active.page.locator('body').innerText().catch(() => ''))
    await shot('a4-agent-lifecycle-failure').catch(() => {})
  }
  process.exitCode = 1
} finally {
  if (active?.browser) await active.browser.close().catch(() => {})
  await writeFile(
    path.join(output, 'device-a4-agent-lifecycle.json'),
    JSON.stringify({ serial, results }, null, 2),
  )
  console.log(JSON.stringify(results, null, 2))
}
