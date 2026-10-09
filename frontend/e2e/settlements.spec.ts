import { expect, test } from '@playwright/test'
import path from 'node:path'
import os from 'node:os'

const csv =
  'statement_id,line_id,entry_type,amount,currency,occurred_at,evidence_ref,settlement_id\nS1,1,payout,80.1234,USD,2026-10-08 08:30:00,P1,SET-1\nS1,2,sale,100,USD,2026-10-07 08:30:00,,SET-1\n'
for (const mobile of [false, true]) {
  test(`settlement cycle manual receipts lifecycle ${mobile ? 'mobile' : 'desktop'}`, async ({
    page,
  }) => {
    test.setTimeout(60000)
    await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 })
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await page.goto('/settlements')
    await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
    await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
    page.on('console', (m) => {
      if (m.type() === 'error') errors.push(m.text())
    })
    const session = (await (await page.request.get('/api/auth/session')).json()) as {
      csrf_token: string
    }
    const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
    const shopResponse = await page.request.post('/api/shops', {
      headers,
      data: {
        code: `settle-${test.info().testId.slice(-12)}`,
        name: '结算合成店',
        platform: 'other',
        market: 'US',
        currency: 'USD',
        timezone: 'Asia/Shanghai',
      },
    })
    expect(shopResponse.ok()).toBeTruthy()
    const shop = ((await shopResponse.json()) as { id: number }).id
    await page.goto(`/imports?shop=${shop}&kind=statements&identity=synthetic&channel=generic`)
    await page.getByLabel('CSV / Excel 文件', { exact: true }).setInputFiles({
      name: 'synthetic-settlement.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(csv),
    })
    await page.getByRole('button', { name: '上传并查看映射' }).click()
    await page.getByRole('button', { name: '校验并预览', exact: true }).click()
    const commit = page.waitForResponse(
      (r) => r.url().includes('/commit') && r.request().method() === 'POST',
    )
    await page.getByRole('button', { name: '确认导入', exact: true }).click()
    const batch = (await (await commit).json()) as { id: number; version: number }
    await page.goto(`/settlements?shop=${shop}`)
    await expect(page).toHaveURL(new RegExp(`/settlements\\?shop=${shop}`))
    await expect(page).toHaveTitle(/SoloOps/)
    await expect(page.getByRole('heading', { name: '结算周期，回款有据。' })).toBeVisible()
    await expect(page.locator('vite-error-overlay')).toHaveCount(0)
    await page.getByLabel('数据身份', { exact: true }).selectOption('synthetic')
    await page.getByLabel('周期开始（含偏移）', { exact: true }).fill('2026-10-07T00:00:00+08:00')
    await page.getByLabel('周期结束（含偏移）', { exact: true }).fill('2026-10-08T00:00:00+08:00')
    await page.screenshot({
      path: path.join(
        os.tmpdir(),
        `soloops-settlements-entry-${mobile ? 'mobile' : 'desktop'}.png`,
      ),
    })
    await page.getByRole('button', { name: '新建结算登记' }).click()
    await page.getByLabel('原账单号', { exact: true }).fill('S1')
    await page.getByLabel('周期依据与核对说明').fill('合成周期依据，银行待核')
    await page.getByRole('button', { name: '添加人工到账凭据' }).click()
    await page.getByLabel('平台回款凭据号 1', { exact: true }).fill('P1')
    await page.getByLabel('人工到账凭据号 1', { exact: true }).fill('BANK-1')
    await page.getByLabel('到账金额 1', { exact: true }).fill('80.1234')
    await page
      .getByLabel('到账时间（含偏移）1', { exact: true })
      .fill('2026-10-08T01:30:00.123456Z')
    await page
      .getByLabel('凭据核验说明 1', { exact: true })
      .fill('合成卖家声明，待银行原始凭据复核')
    await page.getByRole('button', { name: '预览周期与回款' }).click()
    const preview = page.getByRole('region', { name: '结算预览', exact: true })
    await expect(preview).toContainText('凭据金额一致 · 银行待核')
    await expect(preview).toContainText('余额未知')
    const consent = page.getByLabel('我已核对周期、平台来源与人工到账凭据，确认保存本地登记')
    await expect(page.getByRole('button', { name: '保存结算登记', exact: true })).toBeDisabled()
    await consent.check()
    await page.getByLabel('到账金额 1', { exact: true }).fill('79')
    await expect(preview).toHaveCount(0)
    await page.getByRole('button', { name: '预览周期与回款' }).click()
    await expect(preview).toContainText('差额（平台减人工）：1.1234')
    await consent.check()
    await preview.scrollIntoViewIfNeeded()
    await page.screenshot({
      path: path.join(
        os.tmpdir(),
        `soloops-settlements-preview-${mobile ? 'mobile' : 'desktop'}.png`,
      ),
    })
    await page.getByRole('button', { name: '保存结算登记', exact: true }).click()
    const detail = page.getByRole('article', { name: '结算登记详情', exact: true })
    await expect(detail).toContainText('登记依据未变 · 版本 1')
    await detail.getByRole('link', { name: '结算登记固定链接' }).click()
    await page.reload()
    await expect(detail).toContainText('登记依据未变 · 版本 1')
    await expect(page.getByLabel('数据身份', { exact: true })).toHaveValue('synthetic')
    await detail.getByText('展开双方凭据', { exact: true }).click()
    const comparison = detail.locator('.comparison').first()
    await comparison.locator('summary').filter({ hasText: '来源：' }).click()
    await comparison.getByRole('button', { name: '查看来源原始行' }).click()
    await expect(comparison.getByRole('region', { name: '来源原始值' })).toContainText('SET-1')
    await page.getByRole('button', { name: '回读当前账单与凭据' }).click()
    await expect(page.getByRole('region', { name: '结算当前依据', exact: true })).toContainText(
      '尚未重新确认',
    )
    await page.getByRole('button', { name: '修订并重新核对' }).click()
    await page.getByLabel('到账金额 1', { exact: true }).fill('80.1234')
    await page.getByRole('button', { name: '预览周期与回款' }).click()
    await consent.check()
    await page.getByRole('button', { name: '保存结算登记', exact: true }).click()
    await expect(detail).toContainText('版本 2')
    await detail.getByText('登记历史（2）', { exact: true }).click()
    await page.getByRole('button', { name: '读取 v1 依据', exact: true }).click()
    await expect(detail).toContainText('历史正文 v1')
    await expect(detail).toContainText('差额（平台减人工）：1.1234')
    await expect(page.getByRole('button', { name: '修订并重新核对' })).toHaveCount(0)
    await detail.scrollIntoViewIfNeeded()
    await page.screenshot({
      path: path.join(
        os.tmpdir(),
        `soloops-settlements-history-${mobile ? 'mobile' : 'desktop'}.png`,
      ),
    })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBeTruthy()
    await page.getByLabel('我确认处理此版本登记及上述影响').check()
    await page.getByRole('button', { name: '确认处理登记', exact: true }).click()
    await expect(detail).toContainText('已撤销 · 版本 3')
    await page.getByLabel('登记处理', { exact: true }).selectOption('clear')
    await page.getByLabel('我确认处理此版本登记及上述影响').check()
    await page.getByRole('button', { name: '确认处理登记', exact: true }).click()
    await expect(detail).toContainText('已清除 · 版本 4')
    await expect(detail).not.toContainText('合成周期依据')
    await page.getByRole('button', { name: '新建结算登记' }).click()
    await page.getByLabel('原账单号', { exact: true }).fill('S1')
    await page.getByLabel('周期依据与核对说明').fill('合成来源依赖')
    await page.getByRole('button', { name: '预览周期与回款' }).click()
    await expect(preview).toContainText('未登记到账凭据')
    await consent.check()
    await page.getByRole('button', { name: '保存结算登记', exact: true }).click()
    await expect(detail).toContainText('登记依据未变 · 版本 1')
    expect(
      (
        await page.request.post(`/api/imports/${batch.id}/clear`, {
          headers,
          data: { version: batch.version },
        })
      ).ok(),
    ).toBeTruthy()
    await page.getByRole('button', { name: '回读当前账单与凭据' }).click()
    await expect(detail).toContainText('已清除')
    await expect(detail).not.toContainText('合成来源依赖')
    await page.getByLabel('来源渠道', { exact: true }).selectOption('other')
    await expect(detail).toHaveCount(0)
    expect(errors).toEqual([])
  })
}
