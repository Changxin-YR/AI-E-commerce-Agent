import { fillExactTime } from './date-input'
import { expect, test, type Locator, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'

interface SampleFile {
  filename: string
  kind: string
  channel: string
  text: string
}
interface Samples {
  scope: Record<string, string | number>
  files: SampleFile[]
  policies: Record<string, unknown>[]
  boundaries: { duplicate_orders: string; revised_products: string }
}
interface Task {
  id: number
  kind: string
  status: string
  snapshot: { title: string; object_label: string }
}

const python = path.resolve(
  '../backend/.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
)
const samples = JSON.parse(
  execFileSync(python, ['../scripts/foundation_samples.py'], { encoding: 'utf8' }),
) as Samples

async function upload(page: Page, shop: number, file: SampleFile, revise = false): Promise<void> {
  const query = new URLSearchParams({
    shop: String(shop),
    kind: file.kind,
    identity: 'synthetic',
    channel: file.channel,
  })
  await page.goto(`/imports?${query}`)
  await expect(page.getByLabel('所属店铺')).toHaveValue(String(shop))
  await expect(page.getByRole('combobox', { name: '数据身份', exact: true })).toHaveValue(
    'synthetic',
  )
  if (revise) await fillExactTime(page.getByLabel('导出时间（可选）'), new Date().toISOString())
  await page.getByLabel('CSV / Excel 文件').setInputFiles({
    name: file.filename,
    mimeType: 'text/csv',
    buffer: Buffer.from(file.text),
  })
  await page.getByRole('button', { name: '上传并查看映射' }).click()
  await expect(page.getByRole('heading', { name: '02 / 核对字段映射' })).toBeVisible()
  await page.getByRole('button', { name: '校验并预览' }).click()
  if (revise) await page.getByLabel(/已核对旧值与新值，允许更新/).check()
  await page.getByRole('button', { name: '确认导入', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('批次已导入')
}

async function model(page: Page, goal: string, consent: RegExp): Promise<void> {
  await page.getByLabel('运营目标').fill(goal)
  await page.getByText('数据窗口、规则与任务预算', { exact: true }).click()
  await page.getByLabel('模型预算（USD）', { exact: true }).fill('0.03')
  await page.getByLabel(/同意将本次目标文本/).check()
  await page.getByLabel(consent).check()
  await page.getByRole('button', { name: '启动并运行', exact: true }).click()
  await expect(page.getByRole('region', { name: '任务执行详情' })).toContainText('等待审批')
}

async function approveModel(page: Page): Promise<void> {
  const review = page.getByRole('region', { name: '任务执行详情' })
  await review.getByRole('button', { name: '批准当前节点' }).click()
  await review.getByRole('link', { name: /到业务页面复查/ }).click()
}

async function returnTask(page: Page, id: number): Promise<void> {
  await page.getByRole('link', { name: `返回原运营事项 #${id}`, exact: true }).click()
  await expect(page.getByRole('region', { name: '待办审批详情' })).toContainText(`事项 #${id} ·`)
}

async function exportDraft(page: Page, region: Locator, expected: string): Promise<string> {
  await region.getByRole('button', { name: '复制通用草稿' }).click()
  await expect(region).toContainText('已复制通用草稿')
  const copied = await page.evaluate(() => navigator.clipboard.readText())
  expect(copied).toContain(expected)
  expect(copied).toContain('未提交')
  const downloading = page.waitForEvent('download')
  await region.getByRole('button', { name: '下载通用 CSV' }).click()
  const download = await downloading
  const csv = await readFile((await download.path())!, 'utf8')
  expect(csv.charCodeAt(0)).toBe(0xfeff)
  expect(csv).toContain(expected)
  expect(csv).toContain('基础闭环合成店铺 main')
  return download.suggestedFilename()
}

for (const mobile of [false, true]) {
  const stage = mobile ? 'mobile' : 'desktop'

  test(`foundation shared data four workflows source revision and persistence ${stage}`, async ({
    page,
    context,
  }) => {
    test.setTimeout(180000)
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    page.setDefaultTimeout(15000)
    await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 })
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.goto('/')
    await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
    await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
    const session = (await (await page.request.get('/api/auth/session')).json()) as {
      csrf_token: string
    }
    const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
    let shop = 0
    for (const suffix of ['decoy', 'main']) {
      const created = await page.request.post('/api/shops', {
        headers,
        data: {
          code: `foundation-e2e-${stage}-${suffix}`,
          name: `基础闭环合成店铺 ${suffix}`,
          platform: 'other',
          market: 'US',
          currency: 'USD',
          timezone: 'Asia/Shanghai',
        },
      })
      expect(created.ok()).toBeTruthy()
      shop = ((await created.json()) as { id: number }).id
    }
    for (const file of samples.files) await upload(page, shop, file)
    for (const policy of samples.policies) {
      const result = await page.request.post(`/api/shops/${shop}/support/policies`, {
        headers,
        data: { expected_policy_id: null, data: policy },
      })
      expect(result.ok(), await result.text()).toBeTruthy()
    }
    const query = new URLSearchParams({
      ...Object.fromEntries(
        Object.entries(samples.scope).map(([key, value]) => [key, String(value)]),
      ),
      shop: String(shop),
      identity: 'synthetic',
    })
    const home = `/?${query}`
    await page.goto(home)
    await page.getByRole('link', { name: '启动 AI 今日运营概览' }).click()
    await expect(page.getByRole('combobox', { name: '数据身份', exact: true })).toHaveValue(
      'synthetic',
    )
    await expect(page.getByLabel('执行流程')).toHaveValue('daily_model')
    await model(page, '核对本店铺当前资料，列出所有需要处理的事项。', /我已核对运营范围/)
    await expect(page.getByRole('combobox', { name: '检查渠道', exact: true })).toHaveValue(
      'amazon',
    )
    await expect(page.getByLabel('订单起始时间（含时区）')).toHaveValue(
      String(samples.scope.start_at),
    )
    await approveModel(page)
    await expect(page.locator('.task-row')).toHaveCount(5)
    await expect
      .poll(async () =>
        new Date(await page.getByLabel('订单起始时间（含时区偏移）').inputValue()).toISOString(),
      )
      .toBe(new Date(String(samples.scope.start_at)).toISOString())
    await expect
      .poll(async () =>
        new Date(
          await page.getByLabel('订单结束时间（不含，含时区偏移）').inputValue(),
        ).toISOString(),
      )
      .toBe(new Date(String(samples.scope.end_at)).toISOString())
    const tasksResponse = await page.request.get(
      `/api/shops/${shop}/operations/tasks?data_identity=synthetic&channel=amazon`,
    )
    const tasks = ((await tasksResponse.json()) as { items: Task[] }).items
    const inventory = tasks.find((item) => item.kind === 'low_inventory')!
    const margin = tasks.find((item) => item.kind === 'low_margin')!
    const message = tasks.find(
      (item) => item.kind === 'message_review' && item.snapshot.object_label.includes('SYN-MIXED'),
    )!
    expect(inventory && margin && message).toBeTruthy()
    const detail = page.getByRole('region', { name: '待办审批详情' })
    await page.locator('.task-row').filter({ hasText: inventory.snapshot.title }).click()
    await detail.getByRole('link', { name: '核对当前库存' }).click()
    await expect(page.getByLabel('所属店铺')).toHaveValue(String(shop))
    await expect(page.getByLabel('来源渠道')).toHaveValue('amazon')
    await expect(page.getByLabel('搜索 SKU')).toHaveValue('SYN-CUP')
    await expect(page.getByRole('region', { name: '库存核对结果' })).toContainText('低于安全阈值')
    await returnTask(page, inventory.id)
    await detail.getByRole('button', { name: '批准并创建待办' }).click()
    await detail
      .getByLabel('处理备注')
      .fill('已核对导入快照，需要在原渠道确认补货；未修改外部库存。')
    await detail.getByRole('button', { name: '标记完成' }).click()
    await expect(detail.getByRole('heading', { level: 2 })).toContainText('已完成')
    await page.reload()
    await expect(detail.getByLabel('处理备注')).toHaveValue(/已核对导入快照/)
    await detail.getByRole('button', { name: '重新打开待办' }).click()
    await detail.getByRole('button', { name: '标记完成' }).click()
    await page.getByRole('button', { name: '运行今日运营', exact: true }).click()
    await expect(page.locator('.task-row')).toHaveCount(5)
    await page.locator('.task-row').filter({ hasText: margin.snapshot.title }).click()
    await detail.getByRole('link', { name: '查看同范围经营分析' }).click()
    await expect(page.getByLabel('分析店铺')).toHaveValue(String(shop))
    await expect(page.getByLabel('订单来源渠道')).toHaveValue('amazon')
    await page.getByRole('button', { name: '计算并查看证据' }).click()
    const analysis = page.getByRole('region', { name: '分析结果' })
    for (const amount of ['75.00', '62.00', '13.00']) await expect(analysis).toContainText(amount)
    await page.locator('.analysis-line summary').filter({ hasText: 'SYN-O3 /' }).click()
    await expect(page.locator('.analysis-line').filter({ hasText: 'SYN-O3 /' })).toContainText(
      '行退款 5.0000',
    )
    await page.getByRole('link', { name: '打开 AI 经营问数，确认范围与模型预算' }).click()
    await model(page, '哪些商品销量较高但已知毛利偏低，需要核对哪些数据？', /同意发送本次范围/)
    await expect(page.getByRole('region', { name: '经营问数解释' })).toContainText('SYN-CUP')
    await approveModel(page)
    const analysisUrl = page.url()
    const todo = page.getByRole('region', { name: '分析核对待办' })
    await todo.getByRole('button', { name: '标记核对完成' }).click()
    await expect(todo).toContainText('已核对完成')
    await todo.getByRole('button', { name: '重新打开核对待办' }).click()
    await todo.getByRole('button', { name: '标记核对完成' }).click()
    await returnTask(page, margin.id)
    await detail.getByRole('link', { name: '维护此商品 Listing' }).click()
    await page.getByRole('link', { name: '生成 AI Listing 候选' }).click()
    await expect(page.getByLabel('将发送的商品事实')).toContainText('Synthetic steel cup')
    await model(page, '保留全部商品事实，调整标题和参数的展示顺序。', /我已核对上述商品事实/)
    await approveModel(page)
    const listing = page.getByRole('region', { name: 'Listing 审批详情' })
    await listing.getByLabel('拟议标题').fill('Synthetic steel cup')
    await listing.getByRole('button', { name: '保存为新待审版本' }).click()
    await expect(listing).toContainText('人工编辑')
    await listing.getByLabel('我已逐项核对商品事实、差异与影响范围').check()
    await listing.getByRole('button', { name: '批准并在本地生效' }).click()
    await expect(listing).toContainText('本地已批准')
    const firstExport = await exportDraft(page, listing, 'Synthetic steel cup')
    const listingUrl = page.url()
    await page.reload()
    await expect(listing).toContainText('本地已批准')
    await returnTask(page, margin.id)
    await detail.getByRole('button', { name: '批准并创建待办' }).click()
    await detail.getByLabel('处理备注').fill('已回读同范围分析并维护本地文案，费用仍需核对。')
    await detail.getByRole('button', { name: '标记完成' }).click()
    await page.locator('.task-row').filter({ hasText: message.snapshot.object_label }).click()
    await detail.getByRole('link', { name: '处理此客户消息' }).click()
    await page.getByRole('link', { name: '生成 AI 客服候选' }).click()
    const supportData = page.getByLabel('将发送的客服数据')
    await expect(supportData).toContainText('Where is my order? Also refund it.')
    await supportData.getByLabel(/我已人工核验客户与上述全部当前订单行的关联/).check()
    await supportData.getByLabel(/合成基础验收政策 shipping/).check()
    await supportData.getByLabel(/合成基础验收政策 refund/).check()
    await model(page, '核对这条消息的全部诉求，敏感内容交给人工处理。', /我已核对上述消息原文/)
    const candidate = page.getByRole('region', { name: '模型客服候选预览' })
    await expect(candidate).toContainText('需要人工接管')
    await expect(candidate).toContainText('no refund has been confirmed')
    await approveModel(page)
    const draft = page.getByRole('region', { name: '客服草稿详情' })
    await draft
      .getByLabel('回复正文（仅草稿）')
      .fill('Your request is under manual review. No refund has been confirmed.')
    await draft.getByRole('button', { name: '保存修改' }).click()
    await draft.getByRole('button', { name: '存档处理记录' }).click()
    await expect(draft).toContainText('已存档')
    await expect(draft).toContainText('外部未提交')
    const delivery = draft.getByRole('region', { name: '客服审阅与人工交付' })
    await delivery.getByLabel('我已审阅回复全文、目标语言与全部接管提示').check()
    await delivery.getByRole('button', { name: '确认当前版本已审阅' }).click()
    await expect(delivery).toContainText('本版本已审阅')
    await exportDraft(page, delivery, 'No refund has been confirmed.')
    await fillExactTime(
      delivery.getByLabel('人工操作时间（含时区）'),
      new Date(Date.now() - 1000).toISOString(),
    )
    await delivery.getByLabel('原渠道操作方式').fill('合成人工接管演练')
    await delivery.getByLabel('人工操作证据索引').fill(`SYNTHETIC-FOUNDATION-${stage}`)
    await delivery.getByLabel('我确认已在原渠道人工操作，此记录为本人自报').check()
    await delivery.getByRole('button', { name: '登记人工操作', exact: true }).click()
    await expect(delivery).toContainText('人工操作自报已登记')
    const supportUrl = page.url()
    await page.reload()
    await delivery.getByRole('button', { name: '刷新人工操作记录' }).click()
    await expect(delivery).toContainText(`SYNTHETIC-FOUNDATION-${stage}`)
    await expect(draft).toContainText('外部未提交')
    await draft.screenshot({ path: path.join(tmpdir(), `soloops-foundation-support-${stage}.png`) })
    await returnTask(page, message.id)
    await detail.getByRole('button', { name: '批准并创建待办' }).click()
    await detail.getByLabel('处理备注').fill('敏感退款诉求已交人工，草稿已存档，尚未发送。')
    await detail.getByRole('button', { name: '标记完成' }).click()
    await detail.screenshot({ path: path.join(tmpdir(), `soloops-foundation-task-${stage}.png`) })
    await upload(
      page,
      shop,
      { ...samples.files[0]!, text: samples.boundaries.revised_products },
      true,
    )
    await page.goto(analysisUrl)
    await expect(analysis).toContainText('需重新计算')
    await page.goto(listingUrl)
    await expect(listing).toContainText('需重新生成')
    await expect(listing.getByRole('button', { name: '复制通用草稿' })).toBeDisabled()
    await page.locator('.listing-product').filter({ hasText: 'SYN-CUP' }).click()
    await page.getByRole('button', { name: '从商品事实生成草稿' }).click()
    await listing.getByLabel('我已逐项核对商品事实、差异与影响范围').check()
    await listing.getByRole('button', { name: '批准并在本地生效' }).click()
    const freshExport = await exportDraft(page, listing, 'Synthetic steel cup')
    expect(freshExport).not.toBe(firstExport)
    const freshListingUrl = page.url()

    await page.goto(`${home}&task=${margin.id}`)
    await expect(detail.getByRole('heading', { level: 2 })).toContainText('已完成')
    await expect(detail).toContainText('需重新检查')
    const businessReview = detail.getByRole('region', { name: '异常业务复核' })
    await businessReview.getByRole('button', { name: '按原事项复检新来源' }).click()
    await expect(businessReview.getByRole('heading')).toContainText('新来源仍显示异常')
    await expect(detail.getByRole('heading', { level: 2 })).toContainText('已完成')

    await page.getByRole('button', { name: '运行今日运营', exact: true }).click()
    // Changed evidence creates a new candidate; the completed historical task remains stale.
    await expect(page.locator('.task-row')).toHaveCount(6)
    await expect(page.locator('.task-row').filter({ hasText: '来源有效' })).toHaveCount(5)
    await page
      .locator('.task-row')
      .filter({ hasText: margin.snapshot.title })
      .filter({ hasText: '来源有效' })
      .click()
    await detail.getByRole('link', { name: '查看同范围经营分析' }).click()
    await page.getByRole('button', { name: '计算并查看证据' }).click()
    await expect(analysis).toContainText('10.00')
    await page.getByRole('button', { name: '退出', exact: true }).click()
    await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
    await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
    await page.goto(`${home}&task=${margin.id}`)
    await expect(detail.getByRole('heading', { level: 2 })).toContainText('已完成')
    await expect(detail.getByLabel('处理备注')).toHaveValue(/已回读同范围分析/)
    await expect(businessReview.getByRole('heading')).toContainText('新来源仍显示异常')
    await page.goto(supportUrl)
    await delivery.getByRole('button', { name: '刷新人工操作记录' }).click()
    await expect(delivery).toContainText(`SYNTHETIC-FOUNDATION-${stage}`)
    await expect(draft).toContainText('外部未提交')
    await page.goto(freshListingUrl)
    await expect(listing.getByRole('button', { name: '下载通用 CSV' })).toBeEnabled()

    await page.goto('/overview')
    await expect(page.locator('.shop-options input')).not.toHaveCount(0)
    for (const checkbox of await page.locator('.shop-options input').all()) await checkbox.uncheck()
    await page.locator(`.shop-options input[value="${shop}"]`).check()
    await page.getByLabel('数据身份').selectOption('synthetic')
    await page.getByLabel('日期快捷范围').selectOption('custom')
    await page.getByLabel('开始日期（计入）').fill(String(samples.scope.start_at).slice(0, 10))
    await page
      .getByLabel('结束日期（不计入）')
      .fill(new Date(Date.now() + 86400000).toISOString().slice(0, 10))
    await page.getByLabel('统计币种').selectOption('USD')
    await page.getByRole('button', { name: '生成经营总览', exact: true }).click()
    const overview = page.getByRole('region', { name: '经营总览结果', exact: true })
    await expect(overview.getByRole('article', { name: 'USD 汇总' })).toContainText('87.0000')
    await page.getByRole('button', { name: '保存本地摘要' }).click()
    await expect(page.getByText('摘要已保存，可刷新后回读。库存按保存时刻再次核验。')).toBeVisible()
    await page.reload()
    await page
      .getByRole('button', { name: /查看摘要 #/ })
      .first()
      .click()
    await expect(overview.getByRole('article', { name: 'USD 汇总' })).toContainText('87.0000')
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy()
    expect(errors).toEqual([])
  })
}
