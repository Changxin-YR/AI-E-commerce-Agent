import { expect, test } from '@playwright/test'
import path from 'node:path'
import os from 'node:os'

const csv =
  'statement_id,line_id,entry_type,amount,currency,occurred_at,evidence_ref,fee_name\n' +
  'S1,1,fee,12.3456,USD,2026-10-07 08:30:00,R1,Packaging\n' +
  'S1,2,fee,9,CNY,2026-10-07 08:30:00,R2,Unknown\n'

for (const mobile of [false, true]) {
  test(`fee rules preview revision history and lifecycle ${mobile ? 'mobile' : 'desktop'}`, async ({
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
        code: `rules-${test.info().testId.slice(-12)}`,
        name: '费用映射合成店',
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
      name: 'synthetic-rules.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(csv),
    })
    await page.getByRole('button', { name: '上传并查看映射' }).click()
    await page.getByRole('button', { name: '校验并预览', exact: true }).click()
    await page.getByRole('button', { name: '确认导入', exact: true }).click()
    await expect(
      page.getByText('批次已导入。可展开源行核对，重复确认不会重复增加业务记录。', { exact: true }),
    ).toBeVisible()
    await page.getByRole('link', { name: '前往账单费用核对', exact: true }).click()
    await expect(page).toHaveURL(
      (url) =>
        url.pathname === '/statements' &&
        url.searchParams.get('shop') === String(shop) &&
        url.searchParams.get('identity') === 'synthetic' &&
        url.searchParams.get('channel') === 'generic',
    )
    await expect(page).toHaveTitle(/SoloOps/)
    await expect(page.getByRole('heading', { name: '账单与费用，逐行核对。' })).toBeVisible()
    await expect(page.locator('vite-error-overlay')).toHaveCount(0)
    await page.getByLabel('数据身份', { exact: true }).selectOption('synthetic')
    await page.getByLabel('开始时间（含偏移）').fill('2026-10-07T00:00:00+08:00')
    await page.getByLabel('结束时间（含偏移）').fill('2026-10-08T00:00:00+08:00')
    const rules = page.getByRole('region', { name: '收费映射规则', exact: true })
    await rules.getByRole('button', { name: '新建映射规则' }).click()
    await page.getByLabel('完整原始收费名').fill('Packaging')
    await page.getByLabel('统一费用类别').selectOption('packaging')
    await page.getByLabel('本次规则依据与理由').fill('合成收费定义：包装服务')
    await page.getByRole('button', { name: '预览分类变化' }).click()
    const preview = page.getByRole('region', { name: '规则差异预览', exact: true })
    await expect(preview).toContainText('分类结果变化 1 行')
    await expect(preview).toContainText('未匹配规则 · 待核')
    await expect(preview).toContainText('已按规则分类 · 业务待核 包装')
    await preview.locator('summary').filter({ hasText: '来源：' }).click()
    await preview.getByRole('button', { name: '查看来源原始行' }).click()
    await expect(preview.getByRole('region', { name: '来源原始值' })).toContainText('Packaging')
    const save = page.getByRole('button', { name: '保存规则并回读', exact: true })
    await expect(save).toBeDisabled()
    const consent = page.getByLabel(
      '我已核对差异，确认此规则适用于当前店铺、身份、渠道的全部日期与币种',
    )
    await consent.check()
    await page.getByLabel('本次规则依据与理由').fill('合成收费定义：包装服务，人工复核')
    await expect(preview).toHaveCount(0)
    await page.getByRole('button', { name: '预览分类变化' }).click()
    await consent.check()
    await preview.scrollIntoViewIfNeeded()
    await page.screenshot({
      path: path.join(
        os.tmpdir(),
        `soloops-fee-rules-preview-${mobile ? 'mobile' : 'desktop'}.png`,
      ),
    })
    await save.click()
    const detail = page.getByRole('article', { name: '规则详情', exact: true })
    await expect(detail).toContainText('有效 · 版本 1')
    const result = page.getByRole('region', { name: '账单核对结果' })
    await expect(result).toBeVisible()
    await result.getByText('当前收费分类（2 行）', { exact: true }).click()
    await expect(result).toContainText('已按规则分类 · 业务待核')
    await expect(result).toContainText('未匹配规则 · 待核')
    await page.getByLabel('收费分类状态', { exact: true }).selectOption('mapped')
    const mapping = result
      .locator('details')
      .filter({ has: page.getByLabel('收费分类状态', { exact: true }) })
    await mapping.locator('summary').filter({ hasText: '来源：' }).click()
    await mapping.getByRole('button', { name: '查看来源原始行' }).click()
    await expect(mapping.getByRole('region', { name: '来源原始值' })).toContainText('Packaging')
    await rules.getByRole('button', { name: '读取规则列表' }).click()
    await expect(result).toHaveCount(0)
    await rules.getByRole('button', { name: /规则 #.*Packaging.*有效.*v1/ }).click()
    await rules.getByRole('button', { name: '修订此规则' }).click()
    await page.getByLabel('统一费用类别').selectOption('platform')
    await page.getByLabel('本次规则依据与理由').fill('合成定义修订：平台包装服务')
    await page.getByRole('button', { name: '预览分类变化' }).click()
    await expect(preview).toContainText('原规则：Packaging → 包装')
    await expect(preview).toContainText('拟保存：Packaging → 平台服务')
    await consent.check()
    await save.click()
    await expect(detail).toContainText('版本 2')
    await detail.getByText('规则调整历史（2）', { exact: true }).click()
    await expect(detail).toContainText('v1 · 创建')
    await expect(detail).toContainText('v2 · 修订')
    await detail.scrollIntoViewIfNeeded()
    await page.screenshot({
      path: path.join(
        os.tmpdir(),
        `soloops-fee-rules-history-${mobile ? 'mobile' : 'desktop'}.png`,
      ),
    })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBeTruthy()
    await page.getByLabel('我确认处理此版本规则及上述影响').check()
    await page.getByRole('button', { name: '确认处理规则', exact: true }).click()
    await expect(detail).toContainText('已撤销 · 版本 3')
    await expect(result).toBeVisible()
    await result.getByText('当前收费分类（2 行）', { exact: true }).click()
    await page.getByLabel('收费分类状态', { exact: true }).selectOption('mapped')
    await expect(result).toContainText('此筛选无收费分类行')
    await page.getByLabel('规则处理', { exact: true }).selectOption('clear')
    await page.getByLabel('我确认处理此版本规则及上述影响').check()
    await page.getByRole('button', { name: '确认处理规则', exact: true }).click()
    await expect(detail).toContainText('已清除 · 版本 4')
    await expect(detail).not.toContainText('Packaging')
    await detail.getByText('规则调整历史（4）', { exact: true }).click()
    await expect(detail).not.toContainText('合成定义')
    await page.getByLabel('来源渠道', { exact: true }).selectOption('other')
    await expect(detail).toHaveCount(0)
    await expect(result).toHaveCount(0)
    expect(errors).toEqual([])
  })
}
