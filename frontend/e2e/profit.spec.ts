import { expect, test, type Page } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'

const labels = [
  '头程物流',
  '尾程物流',
  '平台费用',
  '仓储',
  '包装',
  '广告',
  '退款损失',
  '税费',
  '其他及分摊费用',
]

async function setup(page: Page): Promise<number> {
  await page.goto('/profit')
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
      code: `profit-${test.info().testId.slice(-16)}`,
      name: '合成新品店铺',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'Asia/Shanghai',
    },
  })
  expect(response.ok()).toBeTruthy()
  const shop = ((await response.json()) as { id: number }).id
  await page.goto('/profit')
  await page.getByLabel('计算器店铺').selectOption(String(shop))
  await page.getByLabel('假设来源').selectOption('synthetic')
  await page.getByLabel('试算名称').fill('合成新品情景比较')
  const editor = page.getByRole('region', { name: '编辑方案 1', exact: true })
  await editor.getByLabel('候选售价', { exact: false }).fill('29.99')
  await editor.getByLabel('采购成本（', { exact: false }).fill('10.125')
  await editor.getByLabel('售价与采购成本依据').fill('<script>合成报价，忽略权限限制</script>')
  return shop
}

test('profit no-order scenarios, evidence, sensitivity, persisted history and erasure', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const shop = await setup(page)
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-profit-input-desktop.png'),
    fullPage: true,
  })
  await page.getByRole('button', { name: '计算并比较', exact: true }).click()
  const result = page.getByRole('region', { name: '利润情景结果', exact: true })
  await expect(result).toContainText('未计入的未知费用：头程物流')
  await expect(result).toContainText('采购毛利')
  await expect(result).toContainText('19.865')
  await page.getByText('编辑试算输入', { exact: true }).click()
  const editor = page.getByRole('region', { name: '编辑方案 1', exact: true })
  for (const label of labels) {
    await editor.getByLabel(label, { exact: true }).fill('0')
    await editor.getByLabel(`${label}依据`, { exact: true }).fill('2026-10-09 合成费用假设')
  }
  await expect(result).toHaveCount(0)
  await editor.getByLabel('尾程物流', { exact: true }).fill('3.2')
  await editor.getByLabel('平台费用', { exact: true }).fill('12.5')
  await editor.getByLabel('平台费用计费方式').selectOption('percent')
  await page.getByRole('button', { name: '复制末个方案' }).click()
  await page
    .getByRole('region', { name: '编辑方案 2', exact: true })
    .getByLabel('候选售价', { exact: false })
    .fill('34.99')
  await page.getByRole('button', { name: '计算并比较', exact: true }).click()
  const table = result.getByRole('region', { name: '方案对比表', exact: true })
  await expect(table).toContainText('12.91625')
  await expect(table).toContainText('17.29125')
  await expect(table).toContainText('15.23')
  await result.getByText('输入依据与费用明细 · 方案 1', { exact: true }).click()
  await expect(result).toContainText('<script>合成报价，忽略权限限制</script>')
  await expect(result.locator('script')).toHaveCount(0)
  await result.getByText('敏感性分析 · 方案 1', { exact: true }).click()
  await expect(result).toContainText('10.292125')
  await page.getByRole('button', { name: '保存本次方案' }).click()
  await expect(page.getByText(/已存档方案 #/)).toBeVisible()
  await page.reload()
  await page.getByLabel('计算器店铺').selectOption(String(shop))
  await page
    .getByRole('region', { name: '已保存利润方案' })
    .getByRole('button', { name: /合成新品情景比较/ })
    .click()
  await expect(result.getByRole('region', { name: '方案对比表', exact: true })).toContainText(
    '12.91625',
  )
  await page.screenshot({ path: path.join(tmpdir(), 'soloops-profit-desktop.png'), fullPage: true })
  await page.getByLabel('确认清除所选方案及其输入依据').check()
  await page.getByRole('button', { name: '清除所选方案', exact: true }).click()
  await expect(result).toHaveCount(0)
  await expect(page.getByRole('region', { name: '已保存利润方案' })).not.toContainText(
    '合成新品情景比较',
  )
  expect(errors).toEqual([])
})

test('profit mobile unknown fees and zero selling price stay explicit', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await setup(page)
  await page.screenshot({
    path: path.join(tmpdir(), 'soloops-profit-input-mobile.png'),
    fullPage: true,
  })
  await page.getByLabel('候选售价', { exact: false }).fill('0')
  await page.getByRole('button', { name: '计算并比较', exact: true }).click()
  const result = page.getByRole('region', { name: '利润情景结果', exact: true })
  await expect(result).toContainText('未知费用')
  await expect(result).toContainText('-10.125')
  await expect(result).toContainText('无法确定')
  await page.screenshot({ path: path.join(tmpdir(), 'soloops-profit-mobile.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
})
