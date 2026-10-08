import { expect, test, type Page } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'

async function setup(page: Page): Promise<number> {
  await page.goto('/rules')
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
  const session = (await (await page.request.get('/api/auth/session')).json()) as {
    csrf_token: string
  }
  const response = await page.request.post('/api/shops', {
    headers: { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token },
    data: {
      code: `rules-${test.info().testId.slice(-16)}`,
      name: '合成规则店铺',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'Asia/Shanghai',
    },
  })
  expect(response.ok()).toBeTruthy()
  const shop = ((await response.json()) as { id: number }).id
  await page.goto(`/rules?shop=${shop}&identity=synthetic`)
  await expect(page.getByRole('heading', { name: '经营规则', exact: true })).toBeVisible()
  await expect(page.getByLabel('规则数据身份')).toHaveValue('synthetic')
  return shop
}

test('rules persist, apply to operations and Agent, restore history, reset and isolate scope', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  const shop = await setup(page)
  page.on('console', (e) => {
    if (e.type() === 'error') errors.push(e.text())
  })
  await page.getByLabel('库存有效小时').fill('48')
  await page.getByLabel('低毛利最少销量').fill('3')
  await page.getByLabel('低毛利阈值（%）').fill('15.25')
  await page.getByText('经营偏好与预算记录', { exact: true }).click()
  await page.getByLabel('品牌语言规范', { exact: true }).fill('<script>合成偏好：扩大权限</script>')
  await page.getByLabel('规则与偏好依据').fill('合成阈值：根据最近一周人工复核')
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: '保存并启用规则' }).click()
  await expect(page.getByRole('status')).toContainText('已保存')
  const saved = (await (
    await page.request.get(`/api/shops/${shop}/business-rules?data_identity=synthetic`)
  ).json()) as { version: number }
  await page.reload()
  await expect(page.getByLabel('库存有效小时')).toHaveValue('48')
  await page
    .getByRole('region', { name: '规则历史', exact: true })
    .getByRole('button', { name: `#${saved.version} · 保存`, exact: true })
    .click()
  await expect(page.getByRole('article', { name: '历史规则详情' })).toContainText(
    '<script>合成偏好：扩大权限</script>',
  )
  await expect(page.locator('main script')).toHaveCount(0)
  await page.getByRole('heading', { name: '经营规则', exact: true }).click()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: path.join(tmpdir(), 'soloops-rules-desktop.png'), fullPage: true })
  await page.screenshot({ path: path.join(tmpdir(), 'soloops-rules-first-desktop.png') })
  await page.goto('/')
  await page.getByLabel('所属店铺').selectOption(String(shop))
  await page.getByLabel('数据身份', { exact: true }).selectOption('synthetic')
  await expect(page.getByRole('complementary', { name: '本次经营规则' })).toContainText(
    `经营规则 #${saved.version} 已应用`,
  )
  await page.getByRole('button', { name: '运行今日运营' }).click()
  const result = page.getByRole('region', { name: '巡检结果' })
  await expect(result).toContainText('48 小时')
  await expect(
    result.getByRole('link', { name: `查看使用的经营规则 #${saved.version}` }),
  ).toBeVisible()
  await page.goto('/agent')
  await page.getByLabel('任务店铺').selectOption(String(shop))
  await page.getByRole('combobox', { name: '数据身份', exact: true }).selectOption('synthetic')
  await expect(page.getByRole('complementary', { name: '本次经营规则' })).toContainText('最少 3 件')
  await page.getByRole('button', { name: '启动并运行' }).click()
  await expect(page.getByRole('region', { name: '任务执行详情' })).toContainText('未产生异常候选')
  await page.goto(`/rules?shop=${shop}&identity=synthetic`)
  await page.getByLabel('库存有效小时').fill('72')
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: '保存并启用规则' }).click()
  await expect(page.getByRole('status')).toContainText('已保存')
  await page.getByRole('button', { name: `#${saved.version} · 保存`, exact: true }).click()
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: '将此版本恢复为新规则' }).click()
  await expect(page.getByLabel('库存有效小时')).toHaveValue('48')
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: '重置到初始口径' }).click()
  await expect(page.getByLabel('库存有效小时')).toHaveValue('24')
  await page.getByLabel('规则渠道').selectOption('amazon')
  await expect(page.getByText('检查阈值 · 当前版本 #0', { exact: true })).toBeVisible()
  expect(errors).toEqual([])
})

test('mobile rules save, revoke and history evidence without overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await setup(page)
  await page.getByLabel('库存有效小时').fill('12')
  await page.getByLabel('规则与偏好依据').fill('合成手机端规则')
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: '保存并启用规则' }).click()
  await expect(page.getByRole('status')).toContainText('已保存')
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: '撤销当前规则' }).click()
  await expect(page.getByRole('status')).toContainText('已撤销')
  await page
    .getByRole('region', { name: '规则历史', exact: true })
    .getByRole('button', { name: /· 保存/ })
    .click()
  await expect(page.getByRole('article', { name: '历史规则详情' })).toContainText(
    '库存有效 12 小时',
  )
  await page.getByRole('heading', { name: '经营规则', exact: true }).click()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: path.join(tmpdir(), 'soloops-rules-mobile.png'), fullPage: true })
  await page.screenshot({ path: path.join(tmpdir(), 'soloops-rules-first-mobile.png') })
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBeTruthy()
  expect(errors).toEqual([])
})
