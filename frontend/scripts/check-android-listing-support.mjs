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

// A4 device acceptance: the Listing and support MVPs plus policy expiry.
const results = []
const record = (check, evidence = {}) => {
  results.push({ check, passed: true, ...evidence })
  console.log(check)
}
let active
await mkdir(output, { recursive: true })

async function allowModel(page) {
  await page.getByText('数据窗口、规则与任务预算', { exact: true }).click()
  await page.getByLabel('模型预算（USD）', { exact: true }).fill('0.03')
}

// The listings workspace link prefills the agent form; the record restore keeps
// the last mode for this shop, so every run starts from the business page.
async function aiListing(page, listingShop) {
  await navigate(page, '/listings')
  await page.locator('#listing-shop').selectOption(String(listingShop))
  await page.locator('#listing-query').fill('A4-BOTTLE')
  await page.getByRole('button', { name: '查找商品' }).click()
  await page.locator('.listing-product', { hasText: 'A4-BOTTLE' }).first().click()
  await page.getByRole('link', { name: '生成 AI Listing 候选' }).click()
  await expect(page.getByLabel('执行流程')).toHaveValue('listing_model')
  await expect(page.getByLabel('数据身份')).toHaveValue('synthetic')
  await expect(page.getByLabel('将发送的商品事实')).toContainText('仅限冷水')
  await page.getByLabel('运营目标').fill('标题突出容量，描述先列使用限制')
  await allowModel(page)
  await page.getByLabel(/同意将本次目标文本/).check()
  await page.getByLabel(/我已核对上述商品事实/).check()
  await page.getByRole('button', { name: '启动并运行', exact: true }).click()
  const review = page.getByRole('region', { name: '任务执行详情' })
  const candidate = page.getByRole('region', { name: '模型 Listing 候选预览' })
  await expect(review).toContainText('等待审批', { timeout: 90000 })
  await expect(candidate).toContainText('容量 500 ml', { timeout: 60000 })
  await expect(candidate).toContainText('仅限冷水')
  return { review, candidate }
}

async function policy(page, shop, code, title, validUntil, topic = 'refund') {
  const created = await call(page, `/shops/${shop}/support/policies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      expected_policy_id: null,
      data: {
        code,
        title,
        topic,
        text: 'Contact support for review.',
        market: 'US',
        channel: 'generic',
        language: 'en',
        data_identity: 'synthetic',
        source: '合成政策文档',
        source_version: 'v1',
        source_confirmed: true,
        valid_from: '2026-01-01T00:00:00Z',
        valid_until: validUntil,
      },
    }),
  })
  expect(created.status, JSON.stringify(created.body)).toBeLessThan(300)
  return created.body.id
}

try {
  active = await restart()
  let { page } = active
  await login(page)

  const stamp = Date.now()
  const listingShop = await createShop(
    page,
    `listing-model-e2e-android-${stamp}`,
    `安卓合成 Listing ${stamp}`,
  )
  const productBatch = await seedImport(
    page,
    listingShop,
    'a4-listing.csv',
    'products',
    'sku,name,facts\nA4-BOTTLE,安卓合成水杯,"容量 500 ml\n仅限冷水\n手洗"\n',
  )

  // Listing MVP: model candidate -> node approval -> local effective version.
  const first = await aiListing(page, listingShop)
  const beforeApproval = await call(page, `/shops/${listingShop}/listings/versions`)
  expect(beforeApproval.body).toEqual([])
  await shot('a4-listing-candidate')
  await first.review.getByRole('button', { name: '批准当前节点' }).click()
  const listingLink = first.review.getByRole('link', { name: /到业务页面复查/ })
  await expect(listingLink).toBeVisible({ timeout: 60000 })
  await listingLink.click()
  await page.waitForLoadState('load')
  const listingReview = page.getByRole('region', { name: 'Listing 审批详情' })
  await expect(listingReview).toContainText('测试替身', { timeout: 60000 })
  await listingReview.getByLabel('我已逐项核对商品事实、差异与影响范围').check()
  await listingReview.getByRole('button', { name: '批准并在本地生效' }).click()
  await expect(listingReview).toContainText('本地已批准', { timeout: 60000 })
  const versions = await call(page, `/shops/${listingShop}/listings/versions`)
  await shot('a4-listing-approved')
  record('listing-model-candidate-and-local-approval', {
    shop: listingShop,
    batch: productBatch,
    versions: versions.body.map((item) => ({ id: item.id, status: item.status })),
  })

  // Listing rejection: a second candidate is saved as a draft and then rejected.
  const second = await aiListing(page, listingShop)
  await second.review.getByRole('button', { name: '批准当前节点' }).click()
  const rejectLink = second.review.getByRole('link', { name: /到业务页面复查/ })
  await expect(rejectLink).toBeVisible({ timeout: 60000 })
  await rejectLink.click()
  await page.waitForLoadState('load')
  await expect(page.getByRole('region', { name: 'Listing 审批详情' })).toBeVisible({
    timeout: 60000,
  })
  await page.getByRole('button', { name: '拒绝此版本' }).click()
  await expect(page.getByRole('region', { name: 'Listing 审批详情' })).toContainText('已拒绝', {
    timeout: 60000,
  })
  const rejected = await call(page, `/shops/${listingShop}/listings/versions`)
  expect(rejected.body.some((item) => item.status === 'rejected')).toBe(true)
  await shot('a4-listing-rejected')
  record('listing-draft-rejection', {
    shop: listingShop,
    versions: rejected.body.map((item) => ({ id: item.id, status: item.status })),
  })

  // Support MVP: policy expiry, model candidate, draft edit and archive.
  const supportShop = await createShop(
    page,
    `support-model-e2e-android-${stamp}`,
    `安卓合成客服 ${stamp}`,
  )
  const messageBatch = await seedImport(
    page,
    supportShop,
    'a4-support.csv',
    'messages',
    'message_id,sent_at,body,language,order_id\n' +
      'A4-M1,2026-10-08T01:00:00Z,Where is my order? Also refund it.,en,O1\n',
  )
  const validPolicy = await policy(
    page,
    supportShop,
    'refund-active',
    '安卓合成有效政策',
    '2099-01-01T00:00:00Z',
  )
  const expiredPolicy = await policy(
    page,
    supportShop,
    'refund-expired',
    '安卓合成过期政策',
    '2026-02-01T00:00:00Z',
  )
  await navigate(page, '/support')
  await page.locator('#support-shop').selectOption(String(supportShop))
  await page.locator('#message-query').fill('A4-M1')
  await page.getByRole('button', { name: '搜索消息' }).click()
  await page.locator('.listing-history', { hasText: 'A4-M1' }).first().click()
  const expiredLine = page.locator('summary', { hasText: '安卓合成过期政策' })
  await expect(expiredLine).toContainText('已过期', { timeout: 60000 })
  await expect(page.locator('summary', { hasText: '安卓合成有效政策' })).toBeVisible()
  await shot('a4-support-policy-expiry')
  record('support-policy-expiry', {
    shop: supportShop,
    policies: [validPolicy, expiredPolicy],
  })

  await page.getByRole('link', { name: '生成 AI 客服候选' }).click()
  await expect(page.getByLabel('执行流程')).toHaveValue('support_model')
  const supportData = page.getByLabel('将发送的客服数据')
  await expect(supportData).toContainText('Where is my order? Also refund it.')
  await supportData.getByLabel(/安卓合成有效政策/).check()
  await page.getByLabel('运营目标').fill('识别全部诉求，核对政策后准备草稿')
  await allowModel(page)
  await page.getByLabel(/同意将本次目标文本/).check()
  await page.getByLabel(/我已核对上述消息原文/).check()
  await page.getByRole('button', { name: '启动并运行', exact: true }).click()
  const supportReview = page.getByRole('region', { name: '任务执行详情' })
  const supportCandidate = page.getByRole('region', { name: '模型客服候选预览' })
  await expect(supportReview).toContainText('等待审批', { timeout: 90000 })
  await expect(supportCandidate).toContainText('需要人工接管', { timeout: 60000 })
  await shot('a4-support-candidate')
  await supportReview.getByRole('button', { name: '批准当前节点' }).click()
  const supportLink = supportReview.getByRole('link', { name: /到业务页面复查/ })
  await expect(supportLink).toBeVisible({ timeout: 60000 })
  await supportLink.click()
  await page.waitForLoadState('load')
  const draft = page.getByRole('region', { name: '客服草稿详情' })
  await expect(draft).toContainText('测试替身', { timeout: 60000 })
  await expect(draft).toContainText('外部未提交')

  // Unsaved客服正文 blocks in-page navigation with the view's own guard; the same
  // edit is then saved and archived.
  await draft.getByLabel('回复正文（仅草稿）').fill('Your request is under manual review.')
  await page.getByRole('button', { name: '全部功能', exact: true }).click()
  await page.locator('.seller-navigation a[href="/imports"]').click()
  await expect(
    page.getByText('正文或人工记录尚未保存，请先保存或放弃修改，再离开当前草稿。'),
  ).toBeVisible({ timeout: 30000 })
  await expect(page).toHaveURL(/\/support/)
  await shot('a4-support-leave-protection')
  await expect(draft.getByLabel('回复正文（仅草稿）')).toHaveValue(
    'Your request is under manual review.',
  )
  await draft.getByRole('button', { name: '保存修改' }).click()
  await expect(draft).toContainText('人工编辑', { timeout: 60000 })
  await draft.getByRole('button', { name: '存档处理记录' }).click()
  await expect(draft).toContainText('已存档', { timeout: 60000 })
  const drafts = await call(page, `/shops/${supportShop}/support/drafts`)
  await shot('a4-support-archived')
  record('support-model-draft-save-archive-and-dirty-navigation-blocked', {
    shop: supportShop,
    batch: messageBatch,
    drafts: drafts.body.map((item) => ({ id: item.id, status: item.status })),
  })
} catch (error) {
  results.push({ check: 'failure', passed: false, message: String(error) })
  if (active?.page) {
    console.log(await active.page.locator('body').innerText().catch(() => ''))
    await shot('a4-listing-support-failure').catch(() => {})
  }
  process.exitCode = 1
} finally {
  if (active?.browser) await active.browser.close().catch(() => {})
  await writeFile(
    path.join(output, 'device-a4-listing-support.json'),
    JSON.stringify({ serial, results }, null, 2),
  )
  console.log(JSON.stringify(results, null, 2))
}
