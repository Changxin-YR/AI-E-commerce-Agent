import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'
import os from 'node:os'
import { randomUUID } from 'node:crypto'

const csv =
  'statement_id,line_id,entry_type,amount,currency,occurred_at,evidence_ref,fee_name,settlement_id,order_id,note\n' +
  [
    'S1,1,fee,12.3456,USD,2026-10-07 08:30:00,EXACT,Packaging,P1,,Synthetic fee',
    'S1,2,fee,9,USD,2026-10-07 08:30:00,DIFF,Shipping,P1,,Synthetic fee',
    'S1,3,fee,5,USD,2026-10-07 08:30:00,DUP,Shipping,P1,,Synthetic duplicate',
    'S1,4,fee,5,USD,2026-10-07 08:30:00,DUP,Shipping,P1,,Synthetic duplicate',
    'S1,5,fee,4,CNY,2026-10-07 08:30:00,FX,Storage,P1,,Synthetic fee',
    'S1,6,fee,3,USD,2026-10-07 08:30:00,BILL-ONLY,Advertising,P1,,Synthetic fee',
    'S1,7,sale,100,USD,2026-10-07 08:30:00,,,P1,,Synthetic sale',
    'S1,8,refund,10,USD,2026-10-07 08:30:00,,,P1,,Synthetic refund',
    'S1,9,payout,80,USD,2026-10-07 08:30:00,,,P1,,Synthetic payout',
  ].join('\n')

async function loadResult(page: Page): Promise<void> {
  await page.getByLabel('数据身份', { exact: true }).selectOption('synthetic')
  await page.getByLabel('开始时间（含偏移）').fill('2026-10-07T00:00:00+08:00')
  await page.getByLabel('结束时间（含偏移）').fill('2026-10-08T00:00:00+08:00')
  await page.getByRole('button', { name: '读取并核对', exact: true }).click()
  await expect(page.getByRole('region', { name: '账单核对结果' })).toBeVisible()
}

for (const mobile of [false, true]) {
  test(`statement import, comparison evidence and lifecycle ${mobile ? 'mobile' : 'desktop'}`, async ({
    page,
  }) => {
    test.setTimeout(60000)
    await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 })
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.goto('/statements')
    await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
    await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })
    const session = (await (await page.request.get('/api/auth/session')).json()) as {
      csrf_token: string
    }
    const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
    const response = await page.request.post('/api/shops', {
      headers,
      data: {
        code: `statement-${test.info().testId.slice(-12)}`,
        name: '账单核对合成店',
        platform: 'other',
        market: 'US',
        currency: 'USD',
        timezone: 'Asia/Shanghai',
      },
    })
    expect(response.ok()).toBeTruthy()
    const shop = ((await response.json()) as { id: number }).id
    for (const reference of ['EXACT', 'DIFF', 'DUP', 'FX', 'MANUAL-ONLY']) {
      const saved = await page.request.post(`/api/shops/${shop}/expenses`, {
        headers,
        data: {
          request_id: randomUUID(),
          confirm: true,
          data_identity: 'synthetic',
          channel: 'generic',
          content: {
            label: `合成费用 ${reference}`,
            category: 'other',
            amount: reference === 'EXACT' ? '12.3456' : '7.0001',
            currency: 'USD',
            occurred_at: '2026-10-07T08:30:00+08:00',
            timezone: 'Asia/Shanghai',
            evidence_ref: reference,
            evidence_note: 'Synthetic receipt',
            allocation: 'shop',
            reason: 'Synthetic comparison',
          },
        },
      })
      expect(saved.ok()).toBeTruthy()
    }
    await page.goto(`/statements?shop=${shop}`)
    await expect(page).toHaveURL(new RegExp(`/statements\\?shop=${shop}$`))
    await expect(page).toHaveTitle(/SoloOps/)
    await expect(page.getByRole('heading', { name: '账单与费用，逐行核对。' })).toBeVisible()
    await expect(page.locator('vite-error-overlay')).toHaveCount(0)
    await page.screenshot({
      path: path.join(os.tmpdir(), `soloops-statements-entry-${mobile ? 'mobile' : 'desktop'}.png`),
    })
    await page.getByLabel('数据身份', { exact: true }).selectOption('synthetic')
    await page.getByRole('link', { name: '导入或查看账单批次' }).click()
    await expect(page.getByLabel('报表类型', { exact: true })).toHaveValue('statements')
    await expect(page.getByLabel('数据身份', { exact: true })).toHaveValue('synthetic')
    await page.getByLabel('CSV / Excel 文件', { exact: true }).setInputFiles({
      name: 'synthetic-statement.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(csv),
    })
    await page.getByRole('button', { name: '上传并查看映射' }).click()
    await page.getByRole('button', { name: '校验并预览', exact: true }).click()
    const commit = page.getByRole('button', { name: '确认导入', exact: true })
    await expect(commit).toBeEnabled()
    await commit.click()
    await expect(
      page.getByText('批次已导入。可展开源行核对，重复确认不会重复增加业务记录。', { exact: true }),
    ).toBeVisible()
    await page.getByRole('link', { name: '前往账单费用核对', exact: true }).click()
    await loadResult(page)
    const result = page.getByRole('region', { name: '账单核对结果' })
    await expect(result).toContainText('有效账单 9 行')
    await expect(result).toContainText('平台记载回款 · 到账待核 · USD 80.0000')
    for (const label of [
      '编号与金额一致（1）',
      '金额差异（1）',
      '仅账单有记录（1）',
      '仅人工费用有记录（1）',
      '重复编号 · 待人工核对（1）',
      '币种不一致（1）',
    ]) {
      await expect(page.getByRole('option', { name: label, exact: true })).toHaveCount(1)
    }
    await page.getByLabel('核对状态', { exact: true }).selectOption('amount_difference')
    await expect(result).toContainText('差额 USD 1.9999')
    const comparison = result.getByRole('article')
    await comparison.getByText('查看两侧依据', { exact: true }).click()
    await comparison.locator('summary').filter({ hasText: '来源：' }).click()
    await comparison.getByRole('button', { name: '查看来源原始行' }).click()
    await expect(comparison.getByRole('region', { name: '来源原始值' })).toContainText('DIFF')
    await result.locator('h3').filter({ hasText: '费用差异清单' }).scrollIntoViewIfNeeded()
    await page.screenshot({
      path: path.join(os.tmpdir(), `soloops-statements-${mobile ? 'mobile' : 'desktop'}.png`),
    })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBeTruthy()
    await result.getByRole('link', { name: /查看账单批次 #/ }).click()
    await page.getByRole('button', { name: '撤销此批次', exact: true }).click()
    await page.getByRole('button', { name: '确认撤销', exact: true }).click()
    await expect(page.getByRole('region', { name: /批次 #/ })).toContainText('已撤销')
    await page.getByRole('button', { name: '清除源数据', exact: true }).click()
    await page.getByRole('button', { name: '确认清除', exact: true }).click()
    await expect(page.getByRole('region', { name: /批次 #/ })).toContainText('已清除')
    await page.getByRole('link', { name: '前往账单费用核对', exact: true }).click()
    await loadResult(page)
    await expect(result).toContainText('有效账单 0 行')
    await expect(
      page.getByRole('option', { name: '仅人工费用有记录（5）', exact: true }),
    ).toHaveCount(1)
    await expect(result).not.toContainText('Synthetic fee')
    await page.getByLabel('来源渠道', { exact: true }).selectOption('other')
    await expect(result).toHaveCount(0)
    expect(errors).toEqual([])
  })
}
