/* global console, process */
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

// A3 business closures on the installed APK: today's operations (local rules) and
// business question answering (deterministic in-process stand-in model).
const results = []
const record = (check, evidence = {}) => {
  results.push({ check, passed: true, ...evidence })
  console.log(check)
}
let active
await mkdir(output, { recursive: true })

async function exactTime(input, value) {
  const details = input.locator('..')
  if ((await details.getAttribute('open')) === null) await details.locator('summary').click()
  await expect(input).toBeEnabled()
  await input.fill(value)
}

try {
  active = await restart()
  let { page } = active
  await login(page)

  const stamp = Date.now()
  const shop = await createShop(page, `question-e2e-android-${stamp}`, `安卓合成 MVP ${stamp}`)
  const products = await seedImport(
    page,
    shop,
    'mvp-products.csv',
    'products',
    'sku,name,unit_cost,cost_currency,facts\nMVP-001,安卓合成商品,18,USD,合成规格\n',
  )
  const orders = await seedImport(
    page,
    shop,
    'mvp-orders.csv',
    'orders',
    'order_id,line_id,sku,quantity,unit_price,currency,ordered_at,status,discount,refund\n' +
      'O-MVP,1,MVP-001,3,20,USD,2026-10-07 12:00:00,paid,0,0\n',
  )
  const inventory = await seedImport(
    page,
    shop,
    'mvp-stock.csv',
    'inventory',
    `sku,available,snapshot_at,safety_threshold\nMVP-001,2,${new Date(
      Date.now() - 3600000,
    ).toISOString()},5\n`,
    true,
  )
  record('seed-scoped-sources', { shop, batches: [products, orders, inventory] })

  // The dashboard loaded its shop list before this shop existed; reload so the
  // in-app selectors see it, and let the shell re-check a stale offline notice.
  await page.reload({ waitUntil: 'load' })
  await login(page)
  const retry = page.getByRole('button', { name: '检查连接' })
  if (await retry.isVisible().catch(() => false)) {
    await retry.click()
    await expect(page.locator('body')).not.toContainText('暂时无法连接服务', { timeout: 60000 })
  }

  // 今日运营: local-rule check, evidence review, approval into a local task.
  await navigate(page, '/')
  await page.locator('#ops-shop').selectOption(String(shop))
  await page.locator('#ops-identity').selectOption('synthetic')
  await page.locator('#ops-channel').selectOption('generic')
  await page.getByRole('button', { name: '运行今日运营' }).click()
  const run = page.getByRole('region', { name: '巡检结果' })
  // Stock below its safety threshold and a low-margin SKU are both real candidates here.
  await expect(run).toContainText('新增候选 2', { timeout: 60000 })
  await page.locator('.task-row', { hasText: '核对低于安全阈值的库存' }).first().click()
  const detail = page.getByRole('region', { name: '待办审批详情' })
  await expect(detail).toContainText('库存阈值')
  await detail.getByLabel('处理备注').fill('安卓合成核对记录')
  await detail.getByRole('button', { name: '批准并创建待办' }).click()
  await expect(detail.getByRole('heading', { name: /事项 #.*待处理/ })).toBeVisible({
    timeout: 60000,
  })
  const tasks = await call(
    page,
    `/shops/${shop}/operations/tasks?data_identity=synthetic&channel=generic&offset=0`,
  )
  const task = tasks.body.items.find((item) => item.kind === 'low_inventory')
  expect(task, JSON.stringify(tasks.body)).toBeTruthy()
  expect(task.status, JSON.stringify(task)).toBe('open')
  expect(task.business_state).toBe('pending_review')
  const other = tasks.body.items.find((item) => item.kind === 'low_margin')
  const runList = await call(
    page,
    `/shops/${shop}/operations/runs?data_identity=synthetic&channel=generic`,
  )
  await shot('mvp-operations-task')
  record('today-operations-candidate-and-task', {
    shop,
    run: runList.body[0].id,
    candidates: tasks.body.items.length,
    task: task.id,
    task_status: task.status,
    business_state: task.business_state,
    note: task.note,
    untouched_candidate: other?.id ?? null,
  })

  // 经营问数: deterministic stand-in model, evidence explanation, approval.
  await navigate(page, '/agent')
  await page.getByLabel('任务店铺').selectOption(String(shop))
  await page.getByLabel('执行流程').selectOption('question')
  await page.getByLabel('数据身份').selectOption('synthetic')
  await expect(page.getByText('模型已配置：synthetic-evidence-model')).toBeVisible({
    timeout: 60000,
  })
  await page
    .getByLabel('运营目标')
    .fill('哪些商品销量较高但已知毛利偏低，需要核对哪些数据？')
  await page.getByText('数据窗口、规则与任务预算', { exact: true }).click()
  await exactTime(page.getByLabel('订单起始时间（含时区）'), '2026-10-07T00:00:00Z')
  await exactTime(page.getByLabel('订单结束时间（不包含）'), '2026-10-08T00:00:00Z')
  await page.getByLabel('模型预算（USD）', { exact: true }).fill('0.03')
  await page.getByLabel(/同意将本次目标文本/).check()
  await page.getByLabel(/同意发送本次范围/).check()
  await page.getByRole('button', { name: '启动并运行', exact: true }).click()
  const review = page.getByRole('region', { name: '任务执行详情' })
  const narrative = page.getByRole('region', { name: '经营问数解释' })
  await expect(review).toContainText('等待审批', { timeout: 90000 })
  await expect(narrative).toContainText('MVP-001', { timeout: 60000 })
  await expect(narrative).toContainText('6.0000 USD')
  const explanation = await narrative.innerText()
  await shot('mvp-question-explanation')
  await review.getByRole('button', { name: '批准当前节点' }).click()
  await expect(review.getByRole('link', { name: /到业务页面复查/ })).toBeVisible({
    timeout: 60000,
  })
  const runs = await call(page, `/shops/${shop}/agent/runs`)
  await shot('mvp-question-approved')
  record('business-question-evidence-and-approval', {
    shop,
    execution: runs.body[0].id,
    model: 'synthetic-evidence-model',
    explanation: explanation.replace(/\s+/g, ' ').slice(0, 400),
  })
} catch (error) {
  results.push({ check: 'failure', passed: false, message: String(error) })
  if (active?.page) {
    console.log(await active.page.locator('body').innerText().catch(() => ''))
    await shot('mvp-failure').catch(() => {})
  }
  process.exitCode = 1
} finally {
  if (active?.browser) await active.browser.close().catch(() => {})
  await writeFile(
    path.join(output, 'device-mvps.json'),
    JSON.stringify({ serial, results }, null, 2),
  )
  console.log(JSON.stringify(results, null, 2))
}
