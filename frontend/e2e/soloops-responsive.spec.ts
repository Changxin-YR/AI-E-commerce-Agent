import { expect, test, type Page, type BrowserContext, type Locator } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'

// Branches select a fixed manifest scenario; they never depend on observed UI state.
/* eslint-disable playwright/no-conditional-in-test, playwright/no-conditional-expect */

// Manifest order, real isolated API, repository-owned synthetic inputs.
const routes = [
  '/login',
  '/',
  '/settings',
  '/imports',
  '/analytics',
  '/listings',
  '/support',
  '/inventory',
  '/agent',
  '/profit',
  '/expenses',
  '/statements',
  '/order-reconciliation',
  '/settlements',
  '/rules',
  '/outbound',
  '/overview',
  '/schedules',
  '/product-quality',
  '/product-edits',
]
const sizes = [
  { width: 1440, height: 1000 },
  { width: 420, height: 900 },
  { width: 390, height: 844 },
]
const output = path.resolve(process.env.UI_EVIDENCE_DIR || '../.local/ui-evidence')
const python = path.resolve(
  '../backend/.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
)
interface SampleFile {
  filename: string
  kind: string
  channel: string
  text: string
}
const samples = JSON.parse(
  execFileSync(python, ['../scripts/foundation_samples.py'], { encoding: 'utf8' }),
) as {
  scope: Record<string, string | number>
  files: SampleFile[]
  policies: Record<string, unknown>[]
}
let shop: number
let cookies: Awaited<ReturnType<BrowserContext['cookies']>>

async function upload(page: Page, file: SampleFile, commit: boolean): Promise<void> {
  await page.goto(
    `/imports?${new URLSearchParams({ shop: String(shop), kind: file.kind, identity: 'synthetic', channel: file.channel })}`,
  )
  await page
    .getByLabel('CSV / Excel 文件')
    .setInputFiles({ name: file.filename, mimeType: 'text/csv', buffer: Buffer.from(file.text) })
  await page.getByRole('button', { name: '上传并查看映射' }).click()
  await expect(page.getByRole('heading', { name: '02 / 核对字段映射' })).toBeVisible()
  if (commit) {
    await page.getByRole('button', { name: '校验并预览' }).click()
    await page.getByRole('button', { name: '确认导入', exact: true }).click()
    await expect(page.getByRole('status')).toContainText('批次已导入')
  }
}

test.beforeAll(async ({ browser }) => {
  test.setTimeout(90000)
  const page = await browser.newPage()
  await page.goto('http://127.0.0.1:5174/login')
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '今日经营，从事实出发。' })).toBeVisible()
  const session = (await (await page.request.get('/api/auth/session')).json()) as {
    csrf_token: string
  }
  const headers = { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }
  const result = await page.request.post('/api/shops', {
    headers,
    data: {
      code: `ui-v21-${Date.now()}`,
      name: 'UI 验收合成店铺',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'Asia/Shanghai',
    },
  })
  expect(result.ok(), await result.text()).toBeTruthy()
  shop = ((await result.json()) as { id: number }).id
  for (const file of samples.files) await upload(page, file, true)
  for (const policy of samples.policies) {
    const response = await page.request.post(`/api/shops/${shop}/support/policies`, {
      headers,
      data: { expected_policy_id: null, data: policy },
    })
    expect(response.ok(), await response.text()).toBeTruthy()
  }
  cookies = await page.context().cookies()
  await page.close()
  await mkdir(output, { recursive: true })
})

async function evidence(page: Page, name: string): Promise<void> {
  // This read-only screenshot collector waits for completed API reads and fonts;
  // business assertions use explicit UI state rather than network quietness.
  // eslint-disable-next-line playwright/no-networkidle
  await page.waitForLoadState('networkidle')
  await page.evaluate(() => document.fonts.ready)
  await page.evaluate(() => window.scrollTo(0, 0))
  const geometry = await page.evaluate(() => {
    const elements = [
      ...document.querySelectorAll<HTMLElement>(
        'main button, main a, main input, main select, main textarea, main summary',
      ),
    ].filter((el) => {
      if (!el.getClientRects().length || getComputedStyle(el).visibility === 'hidden') return false
      for (let ancestor = el.parentElement; ancestor; ancestor = ancestor.parentElement) {
        if (
          ancestor instanceof HTMLDetailsElement &&
          !ancestor.open &&
          !ancestor.querySelector(':scope > summary')?.contains(el)
        )
          return false
      }
      return true
    })
    const controls = elements.map((el) => {
      const r = el.getBoundingClientRect()
      const scrollContainer = el.closest('.table-scroll')
      return {
        tag: el.tagName,
        inputType: el.getAttribute('type'),
        label: el.getAttribute('aria-label') || el.textContent?.trim() || el.id,
        x: r.x,
        y: r.y + scrollY,
        width: r.width,
        height: r.height,
        disabled: el.matches(':disabled'),
        inScrollTable: !!scrollContainer,
      }
    })
    const occluded = elements
      .filter((el) => !el.matches(':disabled'))
      .flatMap((el) => {
        el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' })
        // Wrapped inline links have multiple hit areas; their bounding-box
        // centre can be whitespace between lines rather than clickable text.
        const hits = [...el.getClientRects()].map((r) =>
          document.elementFromPoint(
            Math.max(1, Math.min(innerWidth - 1, r.x + r.width / 2)),
            Math.max(1, Math.min(innerHeight - 1, r.y + r.height / 2)),
          ),
        )
        return hits.some((hit) => hit && (hit === el || el.contains(hit)))
          ? []
          : [
              {
                tag: el.tagName,
                label: el.textContent?.trim() || el.id,
                coveredBy: hits.map((hit) => hit?.tagName),
              },
            ]
      })
    window.scrollTo(0, 0)
    return {
      viewport: { width: innerWidth, height: innerHeight },
      pageWidth: document.documentElement.scrollWidth,
      controls,
      occluded,
    }
  })
  await writeFile(path.join(output, `${name}.json`), JSON.stringify(geometry, null, 2))
  await page.screenshot({ path: path.join(output, `${name}-full.png`), fullPage: true })
  await page.screenshot({ path: path.join(output, `${name}-screen.png`) })
  expect(
    geometry.pageWidth,
    `Page must scroll vertically, tables within their own containers: ${name}`,
  ).toBeLessThanOrEqual(geometry.viewport.width)
  const clipped = geometry.controls.filter(
    (c) => !c.inScrollTable && (c.x < -1 || c.x + c.width > geometry.viewport.width + 1),
  )
  expect(clipped, `Controls outside viewport: ${name}`).toEqual([])
  const narrowDates = geometry.controls.filter(
    (control) => control.inputType === 'datetime-local' && control.width < 240,
  )
  expect(narrowDates, `Date and time must remain readable in full: ${name}`).toEqual([])
  expect(
    geometry.occluded,
    `Enabled controls must be reachable without an overlay: ${name}`,
  ).toEqual([])
}

async function expanded(page: Page, name: string, focus: Locator): Promise<void> {
  await expect(focus).toBeVisible()
  await evidence(page, `${name}-expanded`)
  await focus.scrollIntoViewIfNeeded()
  await page.screenshot({ path: path.join(output, `${name}-expanded-focus.png`) })
  const crop = await page.evaluate(() => ({
    x: scrollX,
    y: scrollY,
    width: innerWidth,
    height: innerHeight,
  }))
  await writeFile(path.join(output, `${name}-expanded-focus.json`), JSON.stringify(crop, null, 2))
}

for (const size of sizes) {
  for (const [index, route] of routes.entries()) {
    test(`SoloOps ${String(index + 1).padStart(2, '0')} ${route} at ${size.width}`, async ({
      page,
      context,
    }) => {
      const errors: string[] = []
      page.on('pageerror', (error) => errors.push(error.message))
      await page.setViewportSize(size)
      if (route !== '/login') await context.addCookies(cookies)
      const query = new URLSearchParams({
        ...Object.fromEntries(
          Object.entries(samples.scope).map(([key, value]) => [key, String(value)]),
        ),
        shop: String(shop),
        identity: 'synthetic',
      })
      await page.goto(route === '/login' ? route : `${route}?${query}`)
      await expect(page.locator('main h1').first()).toBeVisible()
      await expect(page.locator('vite-error-overlay')).toHaveCount(0)
      const name = `${String(index + 1).padStart(2, '0')}-${size.width}`
      await evidence(page, name)
      if (route !== '/login') {
        const nav = page.getByRole('navigation', { name: '主导航' })
        await nav.getByRole('button', { name: '展开全部功能' }).click()
        await expect(nav.getByRole('link')).toHaveCount(19)
        for (const link of await nav.getByRole('link').all()) {
          await link.scrollIntoViewIfNeeded()
          await expect(link).toBeVisible()
          await link.click({ trial: true })
        }
        await nav.getByRole('button', { name: '收起全部功能' }).click()
      }
      if (route === '/login') {
        await page.getByText('首次使用或忘记密码？', { exact: true }).click()
        await expect(page.locator('.login-help[open]')).toContainText('重置密码')
        await expanded(page, name, page.locator('.login-help'))
      }
      if (route === '/imports') {
        await upload(page, samples.files[0]!, false)
        await expanded(page, name, page.getByRole('heading', { name: '02 / 核对字段映射' }))
      }
      if (route === '/analytics') {
        await page.getByRole('button', { name: '计算并查看证据' }).click()
        await expect(page.getByRole('region', { name: '分析结果' })).toContainText('75.00')
        await expanded(page, name, page.getByRole('region', { name: '分析结果' }))
      }
      if (route === '/inventory') {
        await expect(page.getByRole('region', { name: '库存核对结果' })).toContainText(
          '低于安全阈值',
        )
        await page.locator('main summary').filter({ hasText: '来源：' }).first().click()
        await page.getByRole('button', { name: '查看来源原始行' }).first().click()
        await expect(page.getByRole('region', { name: '来源原始值' })).toBeVisible()
        await expanded(page, name, page.getByRole('region', { name: '来源原始值' }))
      }
      if (route === '/') {
        await page.getByRole('button', { name: '运行今日运营', exact: true }).click()
        await expect(page.locator('.task-row').first()).toBeVisible()
        await page.locator('.task-row').first().click()
        await expanded(page, name, page.getByRole('region', { name: '待办审批详情' }))
      }
      if (route === '/support') {
        await page.locator('.support-layout .listing-history').first().click()
        await page.getByRole('button', { name: '生成本地回复草稿' }).click()
        await expect(page.getByRole('button', { name: '生成本地回复草稿' })).toBeEnabled()
        await expanded(page, name, page.getByRole('region', { name: '客服草稿详情' }))
      }
      if (route === '/agent') {
        await page.getByRole('button', { name: '启动并运行', exact: true }).click()
        await expect(page.getByRole('region', { name: '任务执行详情' })).toContainText('等待审批')
        await expect(page.getByRole('button', { name: '启动并运行', exact: true })).toBeEnabled()
        await expanded(page, name, page.getByRole('heading', { name: '为当前预览创建授权' }))
      }
      if (route === '/expenses') {
        await page.getByRole('button', { name: '新增实际费用' }).click()
        await expanded(page, name, page.getByRole('heading', { name: '录入实际费用' }))
      }
      if (route === '/statements') {
        await page.getByRole('button', { name: '新建映射规则' }).click()
        await expanded(page, name, page.getByRole('button', { name: '预览分类变化' }))
      }
      if (route === '/order-reconciliation') {
        await page.getByRole('button', { name: '读取销售与退款待核清单' }).click()
        await expanded(page, name, page.getByRole('region', { name: '订单金额待核清单' }))
      }
      if (route === '/settlements') {
        await page.getByRole('button', { name: '新建结算登记' }).click()
        await page.getByRole('button', { name: '添加人工到账凭据' }).click()
        await expanded(page, name, page.getByRole('heading', { name: '新建周期与人工到账' }))
      }
      if (route === '/rules') {
        await expanded(page, name, page.getByRole('group', { name: /检查阈值 · 当前版本/ }))
      }
      expect(errors).toEqual([])
    })
  }
}
