import { fillExactTime } from './date-input'
import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'
import os from 'node:os'

const orders =
  'order_id,line_id,sku,quantity,unit_price,currency,ordered_at,status,discount,refund\n' +
  [
    'MATCH,1,001,2,19.9999,USD,2026-10-07 08:30:00,paid,1.0001,0',
    'DIFF,1,002,1,10,USD,2026-10-07 08:30:00,paid,1,0',
    'REFUND,1,003,1,10,USD,2026-10-07 08:30:00,partially_refunded,1,3',
    'DUP,1,004,1,10,USD,2026-10-07 08:30:00,paid,1,0',
  ].join('\n')
const statements =
  'statement_id,line_id,entry_type,amount,currency,occurred_at,order_id,note\n' +
  [
    'S1,1,sale,38.9997,USD,2026-10-07 08:30:00,MATCH,Synthetic matched source',
    'S1,2,sale,9.0001,USD,2026-10-07 08:30:00,DIFF,Synthetic difference',
    'S1,3,sale,9,USD,2026-10-07 08:30:00,REFUND,Synthetic sale before refund',
    'S1,4,refund,3,USD,2026-10-07 08:30:00,REFUND,Synthetic refund',
    'S1,5,sale,9,USD,2026-10-07 08:30:00,DUP,Synthetic split',
    'S1,6,sale,9,USD,2026-10-01 08:30:00,DUP,Synthetic outside window',
  ].join('\n')

async function importFile(page: Page, shop: number, kind: string, content: string): Promise<void> {
  await page.goto(`/imports?shop=${shop}&kind=${kind}&identity=synthetic&channel=generic`)
  await expect(page.getByLabel('报表类型', { exact: true })).toHaveValue(kind)
  await page.getByLabel('CSV / Excel 文件', { exact: true }).setInputFiles({
    name: `synthetic-${kind}.csv`,
    mimeType: 'text/csv',
    buffer: Buffer.from(content),
  })
  await page.getByRole('button', { name: '上传并查看映射' }).click()
  await page.getByRole('button', { name: '校验并预览', exact: true }).click()
  await page.getByRole('button', { name: '确认导入', exact: true }).click()
  await expect(
    page.getByText('批次已导入。可展开源行核对，重复确认不会重复增加业务记录。', { exact: true }),
  ).toBeVisible()
}
async function scope(page: Page): Promise<void> {
  await fillExactTime(page.getByLabel('开始时间（含偏移）'), '2026-10-07T00:00:00+08:00')
  await fillExactTime(page.getByLabel('结束时间（含偏移）'), '2026-10-08T00:00:00+08:00')
}
for (const mobile of [false, true]) {
  const size = mobile ? 'mobile' : 'desktop'

  test(`order sales and refund evidence ${mobile ? 'mobile' : 'desktop'}`, async ({ page }) => {
    test.setTimeout(60000)
    await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 })
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.goto('/statements')
    await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
    await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
    page.on('console', (message) => {
      if (message.type() === 'error') errors.push(message.text())
    })
    const session = (await (await page.request.get('/api/auth/session')).json()) as {
      csrf_token: string
    }
    const response = await page.request.post('/api/shops', {
      headers: { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token },
      data: {
        code: `order-check-${test.info().testId.slice(-12)}`,
        name: '订单核对合成店',
        platform: 'other',
        market: 'US',
        currency: 'USD',
        timezone: 'Asia/Shanghai',
      },
    })
    expect(response.ok()).toBeTruthy()
    const shop = ((await response.json()) as { id: number }).id
    await importFile(page, shop, 'orders', orders)
    await importFile(page, shop, 'statements', statements)
    await page.getByRole('link', { name: '前往账单费用核对', exact: true }).click()
    await expect(page).toHaveURL(/\/statements\?/)
    await expect(page.getByRole('heading', { name: '账单与费用，逐行核对。' })).toBeVisible()
    await expect(page.getByLabel('所属店铺', { exact: true })).toHaveValue(String(shop))
    await page.getByLabel('数据身份', { exact: true }).selectOption('synthetic')
    await expect(
      page.getByRole('link', { name: '核对订单销售与退款', exact: true }),
    ).toHaveAttribute(
      'href',
      `/order-reconciliation?shop=${shop}&identity=synthetic&channel=generic`,
    )
    await page.getByRole('link', { name: '核对订单销售与退款', exact: true }).click()
    await expect(page).toHaveURL(/\/order-reconciliation\?/)
    await expect(page).toHaveTitle(/SoloOps/)
    await expect(page.getByRole('heading', { name: '订单与账单，差异有据。' })).toBeVisible()
    await expect(page.locator('vite-error-overlay')).toHaveCount(0)
    await expect(page.getByLabel('所属店铺', { exact: true })).toHaveValue(String(shop))
    await expect(page.getByLabel('数据身份', { exact: true })).toHaveValue('synthetic')
    await scope(page)
    await page.screenshot({ path: path.join(os.tmpdir(), `soloops-order-check-entry-${size}.png`) })
    const read = page.getByRole('button', { name: '读取销售与退款待核清单', exact: true })
    await read.click()
    const result = page.getByRole('region', { name: '订单金额待核清单', exact: true })
    await expect(result).toContainText('销售金额口径：未知')
    await expect(result).toContainText('窗口外关联来源 1 行')
    await expect(result.getByRole('option', { name: '待核实（5）', exact: true })).toHaveCount(1)
    await page
      .getByLabel('销售金额口径', { exact: true })
      .selectOption('merchandise_after_discount')
    await expect(result).toHaveCount(0)
    await expect(read).toBeDisabled()
    await page
      .getByLabel('两侧金额组成依据', { exact: true })
      .fill('合成文件：订单数量×折扣前单价−行折扣；账单销售款为退款前商品款，不含税费运费。')
    await read.click()
    await expect(
      result.getByRole('option', { name: '金额相同（所选口径）（2）', exact: true }),
    ).toHaveCount(1)
    await expect(result.getByRole('option', { name: '待核实（2）', exact: true })).toHaveCount(1)
    await page.getByLabel('订单核对状态', { exact: true }).selectOption('amount_difference')
    await expect(result).toContainText('差额 USD 0.0001')
    const item = result.getByRole('article')
    await item.locator('summary').filter({ hasText: '查看关联来源' }).click()
    const bill = item.locator('.statement-evidence')
    await bill.locator('summary').filter({ hasText: '来源：' }).click()
    await bill.getByRole('button', { name: '查看来源原始行', exact: true }).click()
    await expect(bill.getByRole('region', { name: '来源原始值' })).toContainText(
      'Synthetic difference',
    )
    await result.scrollIntoViewIfNeeded()
    await page.screenshot({
      path: path.join(os.tmpdir(), `soloops-order-check-result-${size}.png`),
    })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBeTruthy()
    await page.getByLabel('订单核对状态', { exact: true }).selectOption('pending')
    await expect(result).toContainText('退款差额未知')
    await expect(result).toContainText('多笔同类型账单')
    await page.getByLabel('订单核对状态', { exact: true }).selectOption('amount_difference')
    await result.getByRole('article').locator('summary').filter({ hasText: '查看关联来源' }).click()
    await result.getByRole('link', { name: /查看账单批次 #/ }).click()
    await page.getByRole('button', { name: '清除源数据', exact: true }).click()
    await page.getByRole('button', { name: '确认清除', exact: true }).click()
    await expect(page.getByRole('region', { name: /批次 #/ })).toContainText('已清除')
    await page.goto(`/order-reconciliation?shop=${shop}&identity=synthetic&channel=generic`)
    await scope(page)
    await read.click()
    await expect(result).toContainText('窗内销售/退款账单 0 行')
    await expect(result).not.toContainText('Synthetic difference')
    await expect(result).toContainText('未找到该类型账单，不代表平台漏记或尚未支付')
    await page.getByLabel('来源渠道', { exact: true }).selectOption('amazon')
    await expect(result).toHaveCount(0)
    await read.click()
    await expect(result).toContainText('无法判断实际销售或退款是否发生')
    expect(errors).toEqual([])
  })
}
