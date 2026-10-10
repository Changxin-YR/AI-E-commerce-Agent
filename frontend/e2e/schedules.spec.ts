import { expect, test, type Page } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'

async function setup(
  page: Page,
): Promise<{ shop: number; batch: number; headers: Record<string, string> }> {
  await page.goto('/schedules')
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
      code: `schedule-${test.info().testId.slice(-16)}`,
      name: '合成定时运营店铺',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'Asia/Shanghai',
    },
  })
  expect(response.ok()).toBeTruthy()
  const shop = ((await response.json()) as { id: number }).id
  const params = new URLSearchParams({
    filename: 'schedule-synthetic.csv',
    kind: 'inventory',
    data_identity: 'synthetic',
    source_channel: 'generic',
    timezone: 'UTC',
  })
  const upload = await page.request.post(`/api/shops/${shop}/imports?${params}`, {
    headers: { ...headers, 'Content-Type': 'text/csv' },
    data: `sku,available,snapshot_at,safety_threshold\nSCHEDULE-001,2,${new Date().toISOString()},5\n`,
  })
  expect(upload.ok()).toBeTruthy()
  const batch = (await upload.json()) as {
    id: number
    version: number
    mapping: Record<string, string>
  }
  const preview = await page.request.post(`/api/imports/${batch.id}/preview`, {
    headers,
    data: { version: batch.version, mapping: batch.mapping },
  })
  expect(preview.ok()).toBeTruthy()
  const checked = (await preview.json()) as { version: number }
  expect(
    (
      await page.request.post(`/api/imports/${batch.id}/commit`, {
        headers,
        data: { version: checked.version },
      })
    ).ok(),
  ).toBeTruthy()
  await page.goto(`/schedules?shop=${shop}`)
  const runtime = page.getByRole('region', { name: '自动调度运行说明' })
  await expect(runtime).toContainText('当前服务关闭自动调度')
  await expect(runtime).toContainText('尚无自动周期记录')
  await expect(runtime).toContainText('电脑关机或休眠期间不运行')
  await runtime.screenshot({
    path: path.join(tmpdir(), `soloops-r2-runtime-${page.viewportSize()!.width}.png`),
  })
  await page.getByRole('button', { name: '新建计划', exact: true }).click()
  await page.getByLabel('检查数据身份').selectOption('synthetic')
  await expect(page.getByText('绑定经营规则版本 #0，使用下方检查阈值')).toBeVisible()
  return { shop, batch: batch.id, headers }
}

async function eraseReport(
  page: Page,
  batch: number,
  headers: Record<string, string>,
  source: boolean,
): Promise<void> {
  if (source) {
    for (const action of ['revoke', 'clear']) {
      const current = (await (await page.request.get(`/api/imports/${batch}`)).json()) as {
        version: number
      }
      expect(
        (
          await page.request.post(`/api/imports/${batch}/${action}`, {
            headers,
            data: { version: current.version },
          })
        ).ok(),
      ).toBeTruthy()
    }
    await page.getByRole('button', { name: '刷新摘要与来源状态' }).click()
  } else {
    await page.getByRole('checkbox', { name: /清除摘要 #/ }).check()
    await page.getByRole('button', { name: '清除所选摘要正文' }).click()
  }
}

for (const mobile of [false, true]) {
  test(`scheduled calendar reports persist and erase ${mobile ? 'mobile' : 'desktop'}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: mobile ? 390 : 1280, height: 844 })
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    const { shop, batch, headers } = await setup(page)
    await page.getByLabel('计划内容').selectOption('report')
    await page.getByLabel('计划名称').fill('每月经营回顾')
    await page.getByLabel('执行周期').selectOption('monthly')
    await expect(page.getByLabel('订单回看天数')).toHaveCount(0)
    await expect(page.getByLabel('每月日期（1–28）')).toHaveCount(0)
    const confirm = page.getByRole('checkbox', { name: /我确认按此周期和范围自动生成/ })
    await confirm.check()
    await page.getByLabel('当地运行时间').fill('10:30')
    await expect(confirm).not.toBeChecked()
    await confirm.check()
    await page.getByRole('button', { name: '保存计划', exact: true }).click()
    const plan = page.getByRole('article', { name: '计划 每月经营回顾', exact: true })
    await expect(plan).toContainText('全部币种分别统计')
    await expect(plan).toContainText('上一完整自然月')
    await plan.getByRole('button', { name: '立即生成报表', exact: true }).click()
    const history = page.getByRole('region', { name: '站内通知与运行历史' })
    await expect(history).toContainText('报表已保存')
    await expect(history.getByRole('link', { name: '查看检查与审批' })).toHaveCount(0)
    await page.reload()
    await expect(history.getByRole('link', { name: '查看报表与依据' })).toBeVisible()
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true)
    await plan.scrollIntoViewIfNeeded()
    await page.screenshot({
      path: path.join(tmpdir(), `soloops-schedule-reports-${mobile ? 'mobile' : 'desktop'}.png`),
      fullPage: false,
    })
    await history.getByRole('link', { name: '查看报表与依据' }).click()
    await expect(page.getByRole('heading', { name: '03 / 当次经营摘要' })).toBeVisible()
    await expect(page.getByText(/自然月报 ·/)).toBeVisible()
    await page.getByText(/当前库存 · 已知低库存/).click()
    await expect(page.getByText('SCHEDULE-001', { exact: false }).first()).toBeVisible()
    await page.reload()
    await expect(page.getByText(/自然月报 ·/)).toBeVisible()
    await eraseReport(page, batch, headers, mobile)
    await expect(page.getByRole('heading', { name: '03 / 当次经营摘要' })).toHaveCount(0)
    await page.goto(`/schedules?shop=${shop}`)
    await history.getByRole('link', { name: '查看报表与依据' }).click()
    await expect(page.getByText('正文已清除', { exact: false }).first()).toBeVisible()
    expect(errors).toEqual([])
  })
}

test('schedule edit pause resume check approval notification readback and revoke', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const { shop } = await setup(page)
  const confirm = page.getByRole('checkbox', { name: /我确认按此周期和范围/ })
  await confirm.check()
  await page.getByLabel('当地运行时间').fill('10:20')
  await expect(confirm).not.toBeChecked()
  await confirm.check()
  await page.getByRole('button', { name: '保存计划', exact: true }).click()
  const plan = page.getByRole('article', { name: '计划 每日运营检查', exact: true })
  await expect(plan).toContainText('已启用')
  await plan.getByRole('button', { name: '修改', exact: true }).click()
  await page.getByLabel('计划名称').fill('周一巡店')
  await page.getByLabel('执行周期').selectOption('weekly')
  await page.getByLabel('星期', { exact: true }).selectOption('0')
  await confirm.check()
  await page.getByRole('button', { name: '保存计划', exact: true }).click()
  const edited = page.getByRole('article', { name: '计划 周一巡店', exact: true })
  await expect(edited).toContainText('星期一')
  await edited.getByRole('button', { name: '暂停', exact: true }).click()
  await expect(edited).toContainText('已暂停')
  await edited.getByRole('button', { name: '恢复', exact: true }).click()
  await edited.getByRole('button', { name: '确认恢复', exact: true }).click()
  await expect(edited).toContainText('已启用')
  await edited.getByRole('button', { name: '立即检查一次', exact: true }).click()
  const history = page.getByRole('region', { name: '站内通知与运行历史' })
  await expect(history).toContainText('等待审批')
  await expect(page.getByRole('region', { name: '自动调度运行说明' })).toContainText(
    '尚无自动周期记录',
  )
  await history.getByRole('link', { name: '查看检查与审批' }).click()
  const review = page.getByRole('region', { name: '任务执行详情' })
  await expect(review).toContainText('SCHEDULE-001')
  await review.getByRole('button', { name: '批准当前节点' }).click()
  await expect(review).toContainText('已完成')
  await page.goto(`/schedules?shop=${shop}`)
  await expect(history).toContainText('等待审批')
  await expect(page.getByRole('region', { name: '自动调度运行说明' })).toContainText(
    '尚无自动周期记录',
  )
  await history.getByRole('button', { name: '标为已读' }).click()
  await expect(history).toContainText('当前没有到期的未读通知')
  await page.getByRole('checkbox', { name: '只看已到提醒时间的未读通知' }).uncheck()
  await expect(history.getByRole('link', { name: '查看检查与审批' })).toBeVisible()
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-schedules-desktop.png'),
    fullPage: false,
  })
  await edited.getByRole('button', { name: '撤销', exact: true }).click()
  await edited.getByRole('button', { name: '确认撤销', exact: true }).click()
  await expect(edited).toContainText('已撤销')
  await page.reload()
  await expect(edited).toContainText('已撤销')
  expect(errors).toEqual([])
})

test('mobile quiet hours history and source erasure', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const { shop, batch, headers } = await setup(page)
  await page.getByLabel('执行周期').selectOption('monthly')
  await page.getByLabel('每月日期（1–28）').fill('12')
  await page.getByRole('checkbox', { name: '启用免打扰时段' }).check()
  const hour = Number(
    new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Shanghai',
      hour: '2-digit',
      hourCycle: 'h23',
    }).format(new Date()),
  )
  await page.getByLabel('免打扰开始小时').fill(String(hour))
  await page.getByLabel('免打扰结束小时').fill(String((hour + 2) % 24))
  await page.getByRole('checkbox', { name: /我确认按此周期和范围/ }).check()
  await page.getByRole('button', { name: '保存计划', exact: true }).click()
  const plan = page.getByRole('article', { name: '计划 每日运营检查', exact: true })
  await expect(plan).toContainText('每月 12 日')
  await plan.getByRole('button', { name: '立即检查一次' }).click()
  const history = page.getByRole('region', { name: '站内通知与运行历史' })
  await expect(history).toContainText('等待审批')
  await expect(page.getByRole('region', { name: '自动调度运行说明' })).toContainText(
    '尚无自动周期记录',
  )
  await page.getByRole('checkbox', { name: '只看已到提醒时间的未读通知' }).check()
  await expect(history).toContainText('当前没有到期的未读通知')
  await page.getByRole('checkbox', { name: '只看已到提醒时间的未读通知' }).uncheck()
  await expect(history).toContainText('等待审批')
  await expect(page.getByRole('region', { name: '自动调度运行说明' })).toContainText(
    '尚无自动周期记录',
  )
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-schedules-mobile.png'),
    fullPage: false,
  })
  for (const action of ['revoke', 'clear']) {
    const current = (await (await page.request.get(`/api/imports/${batch}`)).json()) as {
      version: number
    }
    expect(
      (
        await page.request.post(`/api/imports/${batch}/${action}`, {
          headers,
          data: { version: current.version },
        })
      ).ok(),
    ).toBeTruthy()
  }
  await history.getByRole('link', { name: '查看检查与审批' }).click()
  const review = page.getByRole('region', { name: '任务执行详情' })
  await expect(review).not.toContainText('SCHEDULE-001')
  await expect(review).toContainText('已清除')
  await page.goto(`/schedules?shop=${shop}`)
  await expect(plan).toContainText('已启用')
})
