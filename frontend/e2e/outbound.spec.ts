import { expect, test } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'

test('R2 verified test mailbox preview authorization unknown lookup receipt and replay', async ({
  page,
}) => {
  await page.goto('/outbound')
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  const shops = (await (await page.request.get('/api/shops')).json()) as {
    id: number
    code: string
  }[]
  const shop = shops.find((s) => s.code === 'e2e-outbound')!.id
  const session = (await (await page.request.get('/api/auth/session')).json()) as {
    csrf_token: string
  }
  const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
  const report = await page.request.post(`/api/shops/${shop}/operations/runs`, {
    headers,
    data: {
      request_id: crypto.randomUUID(),
      scope: {
        start_at: '2026-10-07T00:00:00Z',
        end_at: '2026-10-08T00:00:00Z',
        timezone: 'Asia/Shanghai',
        currency: 'USD',
        data_identity: 'synthetic',
      },
    },
  })
  expect(report.ok()).toBeTruthy()
  await page.goto(`/outbound?shop=${shop}`)
  await page.getByLabel('摘要数据身份').selectOption('synthetic')
  await expect(page).toHaveURL(/\/outbound\?shop=/)
  await expect(page).toHaveTitle(/SoloOps/)
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  await page.screenshot({ path: path.join(tmpdir(), 'soloops-outbound-first-desktop.png') })
  const connection = page.getByRole('region', { name: '本人测试邮箱连接' })
  await expect(connection).toContainText('sender@example.invalid')
  await connection.getByRole('checkbox').check()
  await connection.getByRole('button', { name: '连接并发送验证邮件' }).click()
  await expect(connection).toContainText('等待邮箱验证码')
  const inbox = (await (await page.request.get('/api/e2e/synthetic-inbox')).json()) as {
    body: string
  }[]
  const code = inbox[0]!.body.match(/\d{8}/)![0]
  await page.getByLabel('邮箱验证码').fill(code)
  await page.getByRole('button', { name: '验证本人测试邮箱' }).click()
  await expect(connection).toContainText('已验证 / 有效')
  await page.getByRole('button', { name: '生成外发预览' }).click()
  const review = page.getByRole('region', { name: 'R2 外发预览' })
  await expect(review).toContainText('邮件不可撤回')
  await expect(review).toContainText('synthetic')
  await review.getByRole('checkbox').check()
  await review.getByRole('button', { name: '创建限一次预授权' }).click()
  await expect(review).toContainText('剩余 1 次')
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-outbound-preview-desktop.png'),
    fullPage: true,
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.evaluate(() => scrollTo(0, 0))
  await page.screenshot({ path: path.join(tmpdir(), 'soloops-outbound-first-mobile.png') })
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-outbound-preview-mobile.png'),
    fullPage: true,
  })
  await review.getByRole('button', { name: '撤销此授权' }).click()
  await expect(review.getByRole('button', { name: '按有效授权提交一次' })).toHaveCount(0)
  await review.getByRole('checkbox').check()
  await review.getByRole('button', { name: '单次批准并提交' }).click()
  await expect(review).toContainText('结果未知，请回查')
  await page.goto('/')
  const workInbox = page.getByRole('region', { name: '统一工作收件箱' })
  await workInbox.getByLabel('查看店铺').selectOption(String(shop))
  await workInbox.getByLabel('筛选身份').selectOption('synthetic')
  await workInbox.getByLabel('事项类型').selectOption('outbound')
  await expect(workInbox.getByRole('link', { name: '核对 R2 预览与回执' })).toBeVisible()
  await workInbox.getByText('全部与历史 · 原始事项状态', { exact: true }).click()
  await workInbox.getByRole('button', { name: /结果未知/ }).click()
  await workInbox.getByRole('link', { name: '核对 R2 预览与回执' }).click()
  await expect(review).toContainText('结果未知，请回查')
  await review.getByRole('button', { name: '只读回查通道' }).click()
  await expect(review).toContainText('通道报告送达')
  await expect(review).toContainText('尚无实际收件证据')
  await review.getByLabel('实际收件证据说明').fill('本项仅为合成邮箱替身收件，未真实送达。')
  await review.getByRole('checkbox').check()
  await review.getByRole('button', { name: '记录实际收件证据' }).click()
  await expect(review).toContainText('人工收件声明')
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-outbound-mobile.png'),
    fullPage: true,
  })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.setViewportSize({ width: 1280, height: 720 })
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-outbound-desktop.png'),
    fullPage: true,
  })
  await page.reload()
  await expect(review).toContainText('人工收件声明')
  const finalInbox = (await (
    await page.request.get('/api/e2e/synthetic-inbox')
  ).json()) as unknown[]
  expect(finalInbox).toHaveLength(2)
  expect(errors).toEqual([])
})

test('QQ mail previews a chosen recipient and preserves unknown submission after receipt evidence', async ({
  page,
}) => {
  await page.goto('/outbound')
  await page.getByLabel('账号', { exact: true }).fill('e2e_qq_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
  const shops = (await (await page.request.get('/api/shops')).json()) as {
    id: number
    code: string
  }[]
  const shop = shops.find((s) => s.code === 'e2e-qq-mail')!.id
  const session = (await (await page.request.get('/api/auth/session')).json()) as {
    csrf_token: string
  }
  const report = await page.request.post(`/api/shops/${shop}/operations/runs`, {
    headers: { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token },
    data: {
      request_id: crypto.randomUUID(),
      scope: {
        start_at: '2026-10-07T00:00:00Z',
        end_at: '2026-10-08T00:00:00Z',
        timezone: 'Asia/Shanghai',
        currency: 'USD',
        data_identity: 'synthetic',
      },
    },
  })
  expect(report.ok()).toBeTruthy()
  await page.goto(`/outbound?shop=${shop}`)
  await page.getByLabel('摘要数据身份').selectOption('synthetic')
  const connection = page.getByRole('region', { name: '本人测试邮箱连接' })
  await expect(connection).toContainText('QQ 邮箱')
  await connection.getByRole('checkbox').check()
  await connection.getByRole('button', { name: '连接并发送验证邮件' }).click()
  await expect(connection).toContainText('等待邮箱验证码')
  const inbox = (await (await page.request.get('/api/e2e/synthetic-qq-inbox')).json()) as {
    body: string
  }[]
  await page.getByLabel('邮箱验证码').fill(inbox[0]!.body.match(/\d{8}/)![0])
  await page.getByRole('button', { name: '验证本人测试邮箱' }).click()
  await expect(connection).toContainText('已验证 / 有效')
  await expect(page.getByLabel('收件邮箱', { exact: true })).toHaveValue('synthetic-owner@qq.com')
  await page.getByLabel('收件邮箱', { exact: true }).fill('synthetic-recipient@example.net')
  await page.getByRole('button', { name: '生成外发预览' }).click()
  const review = page.getByRole('region', { name: 'R2 外发预览' })
  await expect(review).toContainText('synthetic-recipient@example.net')
  await expect(review).toContainText('这是一份经营检查摘要。')
  await expect(review.getByRole('button', { name: '单次批准并提交' })).toBeDisabled()
  await review.getByRole('checkbox').check()
  await review.getByRole('button', { name: '单次批准并提交' }).click()
  await expect(review).toContainText('结果未知，请回查')
  await expect(review).toContainText('Message-ID')
  await expect(review.getByRole('button', { name: '只读回查通道' })).toHaveCount(0)
  await review
    .getByLabel('实际收件证据说明')
    .fill('合成收件人确认时间、主题及标识；此用例使用邮件替身。')
  await review.getByRole('checkbox').check()
  await review.getByRole('button', { name: '记录实际收件证据' }).click()
  await expect(review).toContainText('人工收件声明')
  await expect(review).toContainText('结果未知，请回查')
  await page.reload()
  await expect(review).toContainText('synthetic-recipient@example.net')
  await expect(review).toContainText('人工收件声明')
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-qq-mail-desktop.png'),
    fullPage: true,
  })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: path.join(tmpdir(), 'soloops-qq-mail-mobile.png'), fullPage: true })
  const sent = (await (await page.request.get('/api/e2e/synthetic-qq-inbox')).json()) as {
    recipient: string
  }[]
  expect(sent).toHaveLength(2)
  expect(sent[1]!.recipient).toBe('synthetic-recipient@example.net')
})
