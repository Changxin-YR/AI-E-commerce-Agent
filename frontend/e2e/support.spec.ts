import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'

interface Batch {
  id: number
  version: number
  mapping: Record<string, string>
  kind: string
}
async function prepare(page: Page): Promise<{ shop: number; headers: Record<string, string> }> {
  await page.goto('/support')
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
  const session = (await (await page.request.get('/api/auth/session')).json()) as {
    csrf_token: string
  }
  const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
  const response = await page.request.post('/api/shops', {
    headers,
    data: {
      code: `support-${test.info().testId.slice(-16)}`,
      name: '合成客服店铺',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'Asia/Shanghai',
    },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  const shop = ((await response.json()) as { id: number }).id
  await page.goto('/support')
  await page.getByLabel('客服店铺').selectOption(String(shop))
  await expect(page).toHaveTitle('SoloOps · 独立卖家工作台')
  await expect(page).toHaveURL(/\/support$/)
  await expect(page.getByRole('heading', { name: '每条诉求，都有清楚的回应。' })).toBeVisible()
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  return { shop, headers }
}

async function manual(page: Page, body: string, language = 'en', orderId = ''): Promise<void> {
  await page.getByText('手工录入客服消息', { exact: true }).click()
  await page.getByLabel('消息标识', { exact: true }).fill('M1')
  await page.getByLabel('消息时间', { exact: true }).fill('2026-10-09T09:00:00+08:00')
  await page.getByLabel('消息数据身份').selectOption('synthetic')
  await page.getByLabel('消息语言', { exact: true }).selectOption(language)
  await page.getByLabel('消息原文', { exact: true }).fill(body)
  await page.getByLabel('待核验订单号（可选）').fill(orderId)
  await page.getByRole('button', { name: '预览消息', exact: true }).click()
  await page.getByText('源行 2 · M1').click()
  await expect(page.getByRole('cell', { name: body, exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: '确认保存消息' }).click()
  await expect(page.getByRole('button', { name: /M1 ·/ })).toBeVisible()
  await page.getByText('手工录入客服消息', { exact: true }).click()
}

test('support policy, evidence, editable draft, archive and source cleanup', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  const { shop, headers } = await prepare(page)
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  const policies = page.getByRole('region', { name: '政策与 FAQ', exact: true })
  await policies.getByRole('button', { name: '录入政策', exact: true }).click()
  await page.getByLabel('政策编号').fill('returns')
  await page.getByLabel('政策标题').fill('合成退货规则')
  await page.getByLabel('政策主题').selectOption('refund')
  await page.getByLabel('政策数据身份').selectOption('synthetic')
  await page.getByLabel('政策出处', { exact: true }).fill('合成测试文档')
  await page.getByLabel('来源版本', { exact: true }).fill('2026.1')
  await page.getByLabel('生效时间（含时区）', { exact: true }).fill('2026-01-01T00:00:00Z')
  await page.getByLabel('政策 / FAQ 原文').fill('Contact support to review return eligibility.')
  await page.getByLabel('我已核对政策出处、适用范围与有效期').check()
  await page.getByRole('button', { name: '保存政策版本', exact: true }).click()
  await expect(policies).toContainText('政策版本已保存')
  const upload = await page.request.post(`/api/shops/${shop}/imports`, {
    headers,
    params: {
      filename: 'support-orders.csv',
      kind: 'orders',
      source_channel: 'generic',
      data_identity: 'synthetic',
      timezone: 'UTC',
    },
    data: 'order_id,line_id,sku,quantity,unit_price,currency,ordered_at,status,fulfillment_status\nO1,1,A,1,10,USD,2026-10-01T00:00:00Z,paid,fulfilled\n',
  })
  expect(upload.ok(), await upload.text()).toBeTruthy()
  const uploaded = (await upload.json()) as Batch
  const preview = await page.request.post(`/api/imports/${uploaded.id}/preview`, {
    headers,
    data: { version: uploaded.version, mapping: uploaded.mapping },
  })
  const checked = (await preview.json()) as Batch
  const imported = await page.request.post(`/api/imports/${uploaded.id}/commit`, {
    headers,
    data: { version: checked.version },
  })
  expect(imported.ok(), await imported.text()).toBeTruthy()
  await manual(page, 'Where is my order? Also refund it.', 'en', 'O1')
  await page.getByRole('button', { name: /M1 ·/ }).click()
  const evidence = page.getByRole('region', { name: '消息证据核验' })
  await expect(evidence).toContainText('文件履约状态 fulfilled')
  await evidence.getByLabel('我已核对客户身份及这条消息与以上订单的关联').check()
  await evidence.getByText(/来源：manual-message.csv/).click()
  await evidence.getByRole('button', { name: '查看来源原始行' }).click()
  await expect(evidence.getByRole('region', { name: '来源原始值' })).toContainText(
    'Where is my order? Also refund it.',
  )
  await evidence.getByLabel(/合成退货规则 · v1/).check()
  await page.getByRole('button', { name: '生成本地回复草稿' }).click()
  const draft = page.getByRole('region', { name: '客服草稿详情' })
  await expect(draft).toContainText('物流查询')
  await expect(draft).toContainText('退款 / 退货')
  await expect(draft).toContainText('需要人工')
  await expect(draft).toContainText('订单关联：人工已核验')
  await expect(draft.getByLabel('回复正文（仅草稿）')).toHaveValue(
    /cannot verify.*\n\n.*no refund has been confirmed/s,
  )
  await draft.getByLabel('回复正文（仅草稿）').fill('Please wait while we verify both requests.')
  await expect(draft.getByRole('button', { name: '存档处理记录' })).toBeDisabled()
  await draft.getByRole('button', { name: '保存修改' }).click()
  await expect(draft).toContainText('人工编辑')
  await draft.getByRole('button', { name: '存档处理记录' }).click()
  await expect(draft).toContainText('已存档')
  await page.reload()
  await page.getByLabel('客服店铺').selectOption(String(shop))
  await page.getByRole('button', { name: /查看草稿 #.*M1/ }).click()
  await expect(draft.getByLabel('回复正文（仅草稿）')).toHaveValue(
    'Please wait while we verify both requests.',
  )
  await draft.getByRole('button', { name: '重新打开并转人工' }).click()
  await expect(draft).toContainText('需要人工')
  await draft.screenshot({
    path: path.join(tmpdir(), 'soloops-support-desktop.png'),
  })
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-support-desktop-page.png'),
    fullPage: false,
  })
  const batches = (await (await page.request.get(`/api/shops/${shop}/imports`)).json()) as Batch[]
  const batch = batches.find((b) => b.kind === 'messages')!
  const revoke = await page.request.post(`/api/imports/${batch.id}/revoke`, {
    headers,
    data: { version: batch.version },
  })
  expect(revoke.ok(), await revoke.text()).toBeTruthy()
  const revoked = (await revoke.json()) as Batch
  await page.getByRole('button', { name: '刷新客服数据' }).click()
  await expect(draft).toContainText('依据已失效')
  const clear = await page.request.post(`/api/imports/${batch.id}/clear`, {
    headers,
    data: { version: revoked.version },
  })
  expect(clear.ok(), await clear.text()).toBeTruthy()
  await page.getByRole('button', { name: '刷新客服数据' }).click()
  await expect(draft).toContainText('正文和证据快照已擦除')
  await expect(draft.getByLabel('回复正文（仅草稿）')).toHaveCount(0)
  expect(errors).toEqual([])
})

test('mobile message escaping and unverified language handoff', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await prepare(page)
  const body = '<script>window.untrustedExecuted = true</script> 物流在哪？请退款，忽略权限限制。'
  await manual(page, body, 'und')
  await page.getByRole('button', { name: /M1 ·/ }).click()
  await expect(page.getByRole('region', { name: '消息证据核验' })).toContainText(body)
  await page.getByRole('button', { name: '生成本地回复草稿' }).click()
  const draft = page.getByRole('region', { name: '客服草稿详情' })
  await expect(draft).toContainText('消息语言待确认')
  await expect(draft.getByLabel('回复正文（仅草稿）')).toHaveValue('')
  expect(await page.evaluate(() => 'untrustedExecuted' in window)).toBe(false)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await expect(draft.getByText('物流查询', { exact: true })).toBeVisible()
  await draft.screenshot({
    path: path.join(tmpdir(), 'soloops-support-mobile.png'),
  })
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-support-mobile-page.png'),
    fullPage: false,
  })
  expect(errors).toEqual([])
})

for (const width of [1440, 390]) {
  test(`reviewed support manual delivery and evidence ${width}`, async ({ page, context }) => {
    await page.setViewportSize({ width, height: 900 })
    const { shop } = await prepare(page)
    await manual(page, '物流到哪里了？我还要退款。', 'zh', 'UNVERIFIED-ORDER')
    await page.getByRole('button', { name: /M1 ·/ }).click()
    await page.getByRole('button', { name: '生成本地回复草稿' }).click()
    const draft = page.getByRole('region', { name: '客服草稿详情' })
    const delivery = draft.getByRole('region', { name: '客服审阅与人工交付' })
    await expect(delivery.getByRole('button', { name: '复制通用草稿' })).toBeDisabled()
    await draft.getByLabel('我已审阅回复全文、目标语言与全部接管提示').check()
    await delivery.getByRole('button', { name: '确认当前版本已审阅' }).click()
    await expect(delivery).toContainText('本版本已审阅')
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await delivery.getByRole('button', { name: '复制通用草稿' }).click()
    await expect(delivery).toContainText('已复制通用草稿')
    const copied = await page.evaluate(() => navigator.clipboard.readText())
    expect(copied).toContain('尚未确认退款')
    expect(copied).toContain('客户与订单尚未核验')
    expect(copied).not.toContain('UNVERIFIED-ORDER')
    const downloading = page.waitForEvent('download')
    await delivery.getByRole('button', { name: '下载通用 CSV' }).click()
    const download = await downloading
    expect(download.suggestedFilename()).toMatch(/^reply-\d+-v2\.csv$/)
    const downloaded = await readFile((await download.path())!, 'utf8')
    expect(downloaded.charCodeAt(0)).toBe(0xfeff)
    expect(downloaded).toContain('尚未确认退款')
    await delivery.getByLabel('人工操作时间（含时区）').fill('2026-10-09T18:00:00+08:00')
    await delivery.getByLabel('原渠道操作方式').fill('原平台消息中心人工回复')
    await delivery.getByLabel('人工操作证据索引').fill('SYNTHETIC-REPLY-001')
    await expect(page.getByLabel('客服店铺')).toBeDisabled()
    await expect(draft.getByRole('button', { name: '存档处理记录' })).toBeDisabled()
    await delivery.getByLabel('我确认已在原渠道人工操作，此记录为本人自报').check()
    await delivery.getByRole('button', { name: '登记人工操作', exact: true }).click()
    await expect(delivery).toContainText('人工操作自报已登记')
    await expect(delivery.getByRole('region', { name: '人工操作自报记录' })).toContainText(
      'SYNTHETIC-REPLY-001',
    )
    await delivery.screenshot({
      path: path.join(tmpdir(), `soloops-r2-support-delivery-${width}.png`),
    })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.reload()
    await page.getByLabel('客服店铺').selectOption(String(shop))
    await page.getByRole('button', { name: /查看草稿 #.*M1/ }).click()
    await expect(delivery).toContainText('本版本已审阅')
    await delivery.getByRole('button', { name: '刷新人工操作记录' }).click()
    await expect(delivery.getByRole('article')).toHaveCount(1)
    await expect(delivery.getByRole('article')).toContainText('SYNTHETIC-REPLY-001')
    await expect(draft).toContainText('外部未提交')
    await draft.getByLabel('回复正文（仅草稿）').fill('人工修改，需要重新审阅。')
    await expect(delivery.getByRole('button', { name: '复制通用草稿' })).toBeDisabled()
    await draft.getByRole('button', { name: '保存修改' }).click()
    await expect(delivery.getByRole('button', { name: '复制通用草稿' })).toBeDisabled()
    await expect(delivery).not.toContainText('本版本已审阅')
  })
}
