import { expect, test } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'

for (const mobile of [false, true]) {
  const stage = mobile ? 'mobile' : 'desktop'

  test(`support model consent handoff approval edit archive and erase ${stage}`, async ({
    page,
  }) => {
    await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1280, height: 800 })
    await page.goto('/support')
    await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
    await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    const session = await (await page.request.get('/api/auth/session')).json()
    const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
    const created = await page.request.post('/api/shops', {
      headers,
      data: {
        code: `support-model-e2e-${stage}`,
        name: '合成客服模型店铺',
        platform: 'other',
        market: 'US',
        currency: 'USD',
        timezone: 'Asia/Shanghai',
      },
    })
    expect(created.ok()).toBeTruthy()
    const shop = (await created.json()).id
    const query = new URLSearchParams({
      filename: 'synthetic-support.csv',
      kind: 'messages',
      data_identity: 'synthetic',
      source_channel: 'generic',
      timezone: 'UTC',
    })
    const uploaded = await page.request.post(`/api/shops/${shop}/imports?${query}`, {
      headers: { ...headers, 'Content-Type': 'text/csv' },
      data: 'message_id,sent_at,body,language,order_id\nMODEL-M1,2026-10-08T01:00:00Z,Where is my order? Also refund it.,en,O1\n',
    })
    expect(uploaded.ok()).toBeTruthy()
    const batch = await uploaded.json()
    const preview = await page.request.post(`/api/imports/${batch.id}/preview`, {
      headers,
      data: { version: batch.version, mapping: batch.mapping },
    })
    expect(preview.ok()).toBeTruthy()
    expect(
      (
        await page.request.post(`/api/imports/${batch.id}/commit`, {
          headers,
          data: { version: (await preview.json()).version },
        })
      ).ok(),
    ).toBeTruthy()
    const policy = await page.request.post(`/api/shops/${shop}/support/policies`, {
      headers,
      data: {
        expected_policy_id: null,
        data: {
          code: 'refund',
          title: '合成退货政策',
          topic: 'refund',
          text: 'Contact support for review.',
          market: 'US',
          channel: 'generic',
          language: 'en',
          data_identity: 'synthetic',
          source: '合成政策文档',
          source_version: 'v1',
          source_confirmed: true,
          valid_from: '2026-01-01T00:00:00Z',
          valid_until: '2099-01-01T00:00:00Z',
        },
      },
    })
    expect(policy.ok()).toBeTruthy()
    const messages = await (await page.request.get(`/api/shops/${shop}/support/messages`)).json()
    await page.goto(`/support?shop=${shop}&message=${messages[0].id}`)
    await page.getByRole('link', { name: '生成 AI 客服候选' }).click()
    await expect(page.getByLabel('执行流程')).toHaveValue('support_model')
    await expect(page.getByLabel('数据身份')).toHaveValue('synthetic')
    const data = page.getByLabel('将发送的客服数据')
    await expect(data).toContainText('Where is my order? Also refund it.')
    await data.getByLabel(/合成退货政策/).check()
    await page.getByLabel('运营目标').fill('识别全部诉求，核对政策后准备草稿')
    await page.getByText('数据窗口、规则与任务预算', { exact: true }).click()
    await page.getByLabel('模型预算（USD）', { exact: true }).fill('0.03')
    await page.getByLabel(/同意将本次目标文本/).check()
    await page.getByLabel(/我已核对上述消息原文/).check()
    await data.getByLabel(/合成退货政策/).uncheck()
    await expect(page.getByLabel(/我已核对上述消息原文/)).not.toBeChecked()
    await expect(page.getByRole('button', { name: '启动并运行', exact: true })).toBeDisabled()
    await data.getByLabel(/合成退货政策/).check()
    await page.getByLabel(/同意将本次目标文本/).check()
    await page.getByLabel(/我已核对上述消息原文/).check()
    await page.getByRole('button', { name: '启动并运行', exact: true }).click()
    const review = page.getByRole('region', { name: '任务执行详情' })
    const candidate = page.getByRole('region', { name: '模型客服候选预览' })
    await expect(review).toContainText('等待审批')
    await expect(candidate).toContainText('需要人工接管')
    await expect(candidate).toContainText('物流查询、退款 / 退货')
    await expect(candidate).toContainText('no refund has been confirmed')
    expect(await (await page.request.get(`/api/shops/${shop}/support/drafts`)).json()).toEqual([])
    await candidate.screenshot({
      path: path.join(tmpdir(), `soloops-support-candidate-${stage}.png`),
    })
    await page.reload()
    await expect(candidate).toContainText('cannot verify the current tracking')
    await review.getByRole('button', { name: '批准当前节点' }).click()
    const link = review.getByRole('link', { name: /到业务页面复查/ })
    await expect(link).toBeVisible()
    const runs = await (await page.request.get(`/api/shops/${shop}/agent/runs`)).json()
    await link.click()
    await expect(page).toHaveURL(/\/support\?shop=.*draft=/)
    const draft = page.getByRole('region', { name: '客服草稿详情' })
    await expect(draft).toContainText('测试替身')
    await expect(draft).toContainText('外部未提交')
    await draft.getByLabel('回复正文（仅草稿）').fill('Your request is under manual review.')
    await draft.getByRole('button', { name: '保存修改' }).click()
    await expect(draft).toContainText('人工编辑')
    await draft.getByRole('button', { name: '存档处理记录' }).click()
    await expect(draft).toContainText('已存档')
    await page.reload()
    await expect(draft.getByLabel('回复正文（仅草稿）')).toHaveValue(
      'Your request is under manual review.',
    )
    await draft.screenshot({ path: path.join(tmpdir(), `soloops-support-archived-${stage}.png`) })
    const current = await (await page.request.get(`/api/imports/${batch.id}`)).json()
    expect(
      (
        await page.request.post(`/api/imports/${batch.id}/clear`, {
          headers,
          data: { version: current.version },
        })
      ).ok(),
    ).toBeTruthy()
    await page.goto(`/agent?shop=${shop}&execution=${runs[0].id}`)
    await expect(review).toContainText('正文已擦除')
    await expect(candidate).toHaveCount(0)
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy()
    expect(errors).toEqual([])
  })
}
