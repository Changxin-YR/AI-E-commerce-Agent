import { expect, test, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'

const password = 'Synthetic-First-Use-2026!'
const python = path.resolve(
  '../backend/.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
)

function prepareAccount(width: number): void {
  const database = process.env.SOLOOPS_TEST_DATABASE_URL
  if (!database || !new URL(database).pathname.endsWith('_test'))
    throw new Error('First-use accounts require an explicit isolated test database')
  // Administrator preparation uses the supported CLI before the seller opens the UI.
  execFileSync(python, ['-m', 'app.cli', 'create-user', `first_use_${width}`, '--password-stdin'], {
    cwd: path.resolve('../backend'),
    input: `${password}\n`,
    env: {
      ...process.env,
      SOLOOPS_DATABASE_URL: database,
      SOLOOPS_MODEL_ENABLED: 'false',
      SOLOOPS_OUTBOUND_ENABLED: 'false',
      SOLOOPS_SCHEDULER_ENABLED: 'false',
    },
  })
}

async function completeOptionalProfile(page: Page, width: number): Promise<void> {
  if (width !== 1440) return
  await page.getByRole('link', { name: '完善经营资料', exact: true }).click()
  await page.getByLabel('经营名称').fill('首次使用合成工作室')
  await page.getByLabel('经营模式').fill('自营')
  await page.getByLabel('主营类目').fill('家居')
  await page.getByRole('button', { name: '保存经营资料' }).click()
  await expect(page.getByRole('status')).toContainText('经营资料已保存')
  await page.getByRole('link', { name: 'SoloOps 首页', exact: true }).click()
}

for (const width of [1440, 390]) {
  test(`preprovisioned seller creates a shop and imports entirely through UI at ${width}px`, async ({
    page,
  }) => {
    prepareAccount(width)
    await page.setViewportSize({ width, height: 900 })
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.goto('/login')
    await page.getByText('首次使用或忘记密码？', { exact: true }).click()
    await expect(page.locator('.login-help')).toContainText('领取工作台网址、账号和密码')
    await expect(page.locator('.login-help')).toContainText('联系管理员')
    await page
      .locator('.login-form-panel')
      .screenshot({ path: `test-results/first-use-login-${width}.png` })
    await page.getByLabel('账号', { exact: true }).fill(`first_use_${width}`)
    await page.getByLabel('密码', { exact: true }).fill(password)
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page.getByRole('heading', { name: '从第一家店铺开始' })).toBeVisible()
    await completeOptionalProfile(page, width)
    await expect(page.getByRole('heading', { name: '从第一家店铺开始' })).toBeVisible()
    await page.getByRole('link', { name: '添加第一家店铺' }).click()
    await expect(page).toHaveURL(/\/settings#shops$/)
    const stores = page.getByRole('region', { name: '店铺记录', exact: true })
    await expect(stores).toBeInViewport()
    await stores.getByRole('button', { name: '添加店铺', exact: true }).click()
    await page.getByLabel('店铺名称').fill(`首次使用合成店 ${width}`)
    await page.getByLabel('店铺标识').fill(`first-use-${width}`)
    await page.getByRole('button', { name: '确认添加' }).click()
    await expect(stores.locator('.shop-row')).toHaveCount(1)
    await page.reload()
    await expect(stores).toContainText(`首次使用合成店 ${width}`)
    await stores.screenshot({ path: `test-results/first-use-shop-${width}.png` })
    await stores.getByRole('link', { name: '导入文件', exact: true }).click()
    await expect(page).toHaveURL(/\/imports\?shop=\d+$/)
    await expect(page.getByLabel('所属店铺').locator('option:checked')).toContainText(
      `first-use-${width}`,
    )
    await expect(page.getByText('第一份文件：', { exact: false })).toBeVisible()
    const downloading = page.waitForEvent('download')
    await page.getByRole('link', { name: '商品模板', exact: true }).click()
    const template = await downloading
    expect(await readFile((await template.path())!, 'utf8')).toContain('sku')
    await page.getByRole('combobox', { name: '数据身份', exact: true }).selectOption('synthetic')
    await page.getByLabel('CSV / Excel 文件').setInputFiles({
      name: 'first-products-synthetic.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(
        'sku,name,facts,price,currency,unit_cost,cost_currency\nFIRST-CUP,合成杯,Capacity: 400ml,10,USD,3,USD\n',
      ),
    })
    await page.getByRole('button', { name: '上传并查看映射' }).click()
    await expect(page.getByRole('heading', { name: '02 / 核对字段映射' })).toBeVisible()
    await page.getByRole('button', { name: '校验并预览' }).click()
    await page.getByRole('button', { name: '确认导入', exact: true }).click()
    await expect(page.getByRole('status')).toContainText('批次已导入')
    await page.reload()
    await expect(page.locator('.batch-history')).toHaveCount(1)
    await expect(page.locator('.batch-history')).toContainText('1 行 · 已导入')
    await page.getByRole('button', { name: /查看批次 #/ }).click()
    await expect(page.getByRole('button', { name: '撤销此批次', exact: true })).toBeVisible()
    await page.locator('.source-row summary').filter({ hasText: 'FIRST-CUP' }).click()
    await expect(page.getByText('FIRST-CUP', { exact: true }).first()).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect(errors).toEqual([])
  })
}
