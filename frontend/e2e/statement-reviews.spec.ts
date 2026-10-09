import { expect, test } from '@playwright/test'
import path from 'node:path'
import os from 'node:os'

const scope = {
  data_identity: 'synthetic',
  channel: 'generic',
  timezone: 'Asia/Shanghai',
  start_at: '2026-10-07T00:00:00+08:00',
  end_at: '2026-10-08T00:00:00+08:00',
}
const csv =
  'statement_id,line_id,entry_type,amount,currency,occurred_at,evidence_ref,fee_name\nS1,1,fee,12.3456,USD,2026-10-07 08:30:00,R1,Packaging\n'
for (const mobile of [false, true]) {
  test(`statement review archive lifecycle ${mobile ? 'mobile' : 'desktop'}`, async ({ page }) => {
    test.setTimeout(60000)
    await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 })
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await page.goto('/statements')
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
    const response = await page.request.post('/api/shops', {
      headers,
      data: {
        code: `review-${test.info().testId.slice(-12)}`,
        name: '核对存档合成店',
        platform: 'other',
        market: 'US',
        currency: 'USD',
        timezone: 'Asia/Shanghai',
      },
    })
    expect(response.ok()).toBeTruthy()
    const shop = ((await response.json()) as { id: number }).id
    await page.goto(`/imports?shop=${shop}&kind=statements&identity=synthetic&channel=generic`)
    await page.getByLabel('CSV / Excel 文件', { exact: true }).setInputFiles({
      name: 'synthetic-review.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(csv),
    })
    await page.getByRole('button', { name: '上传并查看映射' }).click()
    await page.getByRole('button', { name: '校验并预览', exact: true }).click()
    const committed = page.waitForResponse(
      (r) => r.url().includes('/commit') && r.request().method() === 'POST',
    )
    await page.getByRole('button', { name: '确认导入', exact: true }).click()
    const batch = (await (await committed).json()) as { id: number; version: number }
    const content = {
      label: '合成包装费',
      category: 'packaging',
      amount: '12.3456',
      currency: 'USD',
      occurred_at: '2026-10-07T08:30:00+08:00',
      timezone: 'Asia/Shanghai',
      evidence_ref: 'R1',
      evidence_note: '合成包装收据',
      allocation: 'shop',
      reason: '合成核对',
    }
    const feeResponse = await page.request.post(`/api/shops/${shop}/expenses`, {
      headers,
      data: {
        request_id: crypto.randomUUID(),
        confirm: true,
        version: 0,
        data_identity: 'synthetic',
        channel: 'generic',
        content,
      },
    })
    expect(feeResponse.ok()).toBeTruthy()
    const fee = (await feeResponse.json()) as { id: number; version: number }
    const ruleDraft = {
      scope,
      rule_id: null,
      version: 0,
      content: { fee_name: 'Packaging', category: 'packaging', reason: '合成收费定义' },
    }
    const rulePreview = await page.request.post(`/api/shops/${shop}/fee-rules/preview`, {
      headers,
      data: ruleDraft,
    })
    expect(rulePreview.ok()).toBeTruthy()
    const ruleHash = ((await rulePreview.json()) as { preview_hash: string }).preview_hash
    expect(
      (
        await page.request.post(`/api/shops/${shop}/fee-rules`, {
          headers,
          data: {
            ...ruleDraft,
            preview_hash: ruleHash,
            confirm: true,
            request_id: crypto.randomUUID(),
          },
        })
      ).ok(),
    ).toBeTruthy()
    await page.goto(`/statements?shop=${shop}`)
    await expect(page).toHaveTitle(/SoloOps/)
    await expect(page.getByRole('heading', { name: '账单与费用，逐行核对。' })).toBeVisible()
    await expect(page.locator('vite-error-overlay')).toHaveCount(0)
    await page.getByLabel('数据身份', { exact: true }).selectOption('synthetic')
    await page.getByLabel('开始时间（含偏移）').fill(scope.start_at)
    await page.getByLabel('结束时间（含偏移）').fill(scope.end_at)
    const reviews = page.getByRole('region', { name: '人工核对存档', exact: true })
    await reviews.getByRole('button', { name: '新建核对结论' }).click()
    await page.getByLabel('人工结论', { exact: true }).selectOption('consistent')
    await page.getByLabel('核对依据与差异说明').fill('合成编号、币种、金额及收费类别逐行一致')
    await page.getByRole('button', { name: '预览结论与依据' }).click()
    const preview = page.getByRole('region', { name: '核对结论预览', exact: true })
    await expect(preview).toContainText('本窗口费用一致')
    const consent = page.getByLabel('我已核对本窗口的来源、费用、规则和差异说明，确认保存人工结论')
    await expect(page.getByRole('button', { name: '保存核对结论', exact: true })).toBeDisabled()
    await consent.check()
    await page
      .getByLabel('核对依据与差异说明')
      .fill('合成编号、币种、金额及收费类别一致，已核对原行')
    await expect(preview).toHaveCount(0)
    await page.getByRole('button', { name: '预览结论与依据' }).click()
    await consent.check()
    await preview.scrollIntoViewIfNeeded()
    await page.screenshot({
      path: path.join(
        os.tmpdir(),
        `soloops-statement-reviews-preview-${mobile ? 'mobile' : 'desktop'}.png`,
      ),
    })
    await page.getByRole('button', { name: '保存核对结论', exact: true }).click()
    const detail = page.getByRole('article', { name: '核对存档详情', exact: true })
    await expect(detail).toContainText('当前有效 · 版本 1')
    await detail.getByRole('link', { name: '核对存档固定链接' }).click()
    await page.reload()
    await expect(detail).toContainText('当前有效 · 版本 1')
    await expect(page.getByLabel('数据身份', { exact: true })).toHaveValue('synthetic')
    await detail.getByText('展开该版本的存档依据', { exact: true }).click()
    await detail.getByText('全部存档账单明细（1）', { exact: true }).click()
    const evidence = detail
      .getByRole('region', { name: '账单核对结果', exact: true })
      .locator('details')
      .filter({ has: page.getByText('全部存档账单明细（1）', { exact: true }) })
    await evidence.locator('summary').filter({ hasText: '来源：' }).click()
    await evidence.getByRole('button', { name: '查看来源原始行' }).click()
    await expect(evidence.getByRole('region', { name: '来源原始值' })).toContainText('Packaging')
    await page.getByRole('button', { name: '回读当前来源、费用与规则' }).click()
    await expect(page.getByRole('region', { name: '存档当前依据', exact: true })).toContainText(
      '尚未重新确认',
    )
    expect(
      (
        await page.request.post(`/api/shops/${shop}/expenses/${fee.id}`, {
          headers,
          data: {
            request_id: crypto.randomUUID(),
            confirm: true,
            version: fee.version,
            data_identity: 'synthetic',
            channel: 'generic',
            content: { ...content, amount: '20' },
          },
        })
      ).ok(),
    ).toBeTruthy()
    await page.getByRole('button', { name: '回读当前来源、费用与规则' }).click()
    await expect(detail).toContainText('依据已变化 · 待重核')
    await page.getByRole('button', { name: '修订并重新核对' }).click()
    await page.getByLabel('人工结论', { exact: true }).selectOption('differences_recorded')
    await page
      .getByLabel('核对依据与差异说明')
      .fill('合成差异 -7.6544 USD：待卖家核查收据修订，未付款')
    await page.getByRole('button', { name: '预览结论与依据' }).click()
    await consent.check()
    await page.getByRole('button', { name: '保存核对结论', exact: true }).click()
    await expect(detail).toContainText('版本 3')
    await detail.getByText('结论历史（2）', { exact: true }).click()
    await page.getByRole('button', { name: '读取 v1 依据', exact: true }).click()
    await expect(detail).toContainText('历史正文 v1 · 本窗口费用一致')
    await expect(page.getByRole('button', { name: '修订并重新核对' })).toHaveCount(0)
    await detail.getByText('结论历史（2）', { exact: true }).click()
    await page.getByRole('button', { name: '读取 v3 依据', exact: true }).click()
    await detail.scrollIntoViewIfNeeded()
    await page.screenshot({
      path: path.join(
        os.tmpdir(),
        `soloops-statement-reviews-history-${mobile ? 'mobile' : 'desktop'}.png`,
      ),
    })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBeTruthy()
    await page.getByLabel('我确认处理此版本结论及上述影响').check()
    await page.getByRole('button', { name: '确认处理结论', exact: true }).click()
    await expect(detail).toContainText('已撤销 · 版本 4')
    await page.getByLabel('结论处理', { exact: true }).selectOption('clear')
    await page.getByLabel('我确认处理此版本结论及上述影响').check()
    await page.getByRole('button', { name: '确认处理结论', exact: true }).click()
    await expect(detail).toContainText('已清除 · 版本 5')
    await expect(detail).not.toContainText('合成差异')
    await reviews.getByRole('button', { name: '新建核对结论' }).click()
    await page.getByLabel('核对依据与差异说明').fill('合成来源依赖：清除原账单时一起清除')
    await page.getByRole('button', { name: '预览结论与依据' }).click()
    await consent.check()
    await page.getByRole('button', { name: '保存核对结论', exact: true }).click()
    await expect(detail).toContainText('当前有效 · 版本 1')
    const archiveLink = detail.getByRole('link', { name: '核对存档固定链接' })
    await expect(archiveLink).toHaveAttribute('href', /review=\d+/)
    const href = await archiveLink.getAttribute('href')
    expect(
      (
        await page.request.post(`/api/imports/${batch.id}/clear`, {
          headers,
          data: { version: batch.version },
        })
      ).ok(),
    ).toBeTruthy()
    await page.goto(href!)
    await expect(detail).toContainText('已清除')
    await expect(detail).not.toContainText('合成来源依赖')
    await page.getByLabel('来源渠道', { exact: true }).selectOption('other')
    await expect(detail).toHaveCount(0)
    expect(errors).toEqual([])
  })
}
