/* global console, process, window, document */
import { expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import {
  output,
  serial,
  restart,
  login,
  navigate,
  shot,
  call,
  seedImport,
  createShop,
} from './android-device.mjs'

// A5 device acceptance for the remaining business modules: every existing entry
// point gets a real read (or its documented empty state) against one seeded
// synthetic shop. No module is reported as verified without an on-device result.
const results = []
const record = (check, evidence = {}) => {
  results.push({ check, passed: true, ...evidence })
  console.log(check)
}
let active
await mkdir(output, { recursive: true })

async function expandSections(page) {
  for (const details of await page.locator('main details').all()) {
    if ((await details.getAttribute('open')) === null) {
      await details.locator('summary').first().click().catch(() => {})
    }
  }
}

// Shop pickers mount after the page loads its shop list; poll for the option by
// value (shop id) instead of assuming the select exists right after navigation.
async function selectShop(page, shop) {
  const deadline = Date.now() + 90000
  while (Date.now() < deadline) {
    const selects = page.locator('main select')
    const count = await selects.count()
    for (let i = 0; i < count; i++) {
      const select = selects.nth(i)
      if (!(await select.isVisible())) continue
      if ((await select.locator(`option[value="${shop}"]`).count()) > 0) {
        await select.selectOption(String(shop))
        return true
      }
    }
    await page.waitForTimeout(500)
  }
  return false
}

// Seeded rows are synthetic, so pages with a data-identity selector must switch
// away from the default user-import scope before any read is asserted. A shop
// change reloads the scope, so retry until the synthetic option actually sticks.
async function selectIdentity(page) {
  for (let attempt = 0; attempt < 6; attempt++) {
    const selects = page.locator('main select')
    const count = await selects.count()
    for (let i = 0; i < count; i++) {
      const select = selects.nth(i)
      if (!(await select.isVisible())) continue
      if ((await select.locator('option[value="synthetic"]').count()) === 0) continue
      await select.selectOption('synthetic')
      await page.waitForTimeout(800)
      if ((await select.inputValue()) === 'synthetic') return true
    }
    await page.waitForTimeout(800)
  }
  return false
}

// A page that writes its record link can push the route back after we leave, so
// re-check the route once the view has settled.
async function ensureRoute(page, route) {
  for (let attempt = 0; attempt < 3; attempt++) {
    await navigate(page, route)
    await page.waitForTimeout(1500)
    const url = page.url()
    const ok = route === '/' ? /\/$/.test(url) : url.includes(route)
    if (ok) return true
  }
  return false
}

try {
  active = await restart()
  let { page } = active
  await login(page)

  const stamp = Date.now()
  const shopName = `安卓合成A5模块 ${stamp}`
  const shop = await createShop(page, `modules-e2e-android-${stamp}`, shopName)
  const products = await seedImport(
    page,
    shop,
    'a5-products.csv',
    'products',
    'sku,name,unit_cost,cost_currency,facts\nA5-SKU,安卓合成模块商品,18,USD,容量 400 ml\n',
  )
  const orders = await seedImport(
    page,
    shop,
    'a5-orders.csv',
    'orders',
    'order_id,line_id,sku,quantity,unit_price,currency,ordered_at,status,discount,refund\n' +
      'O-A5,1,A5-SKU,3,20,USD,2026-10-07 12:00:00,paid,0,0\n',
  )
  const inventory = await seedImport(
    page,
    shop,
    'a5-stock.csv',
    'inventory',
    `sku,available,snapshot_at,safety_threshold\nA5-SKU,2,${new Date(
      Date.now() - 3600000,
    ).toISOString()},5\n`,
    true,
  )
  const messages = await seedImport(
    page,
    shop,
    'a5-messages.csv',
    'messages',
    'message_id,sent_at,body,language,order_id\nA5-M1,2026-10-08T01:00:00Z,Where is my order?,en,O-A5\n',
  )
  record('module-sources-seeded', { shop, batches: [products, orders, inventory, messages] })

  const specs = [
    { slug: 'dashboard', path: '/', label: '工作台', expect: '今日运营' },
    { slug: 'imports', path: '/imports', label: '数据导入', expect: 'a5-products.csv' },
    { slug: 'agent', path: '/agent', label: '任务执行台', expect: '启动任务' },
    { slug: 'listings', path: '/listings', label: 'Listing 审批', expect: 'A5-SKU' },
    {
      slug: 'listings-generate',
      path: '/listings',
      label: 'Listing 本地模板',
      prepare: async (page) => {
        await page.locator('.listing-product', { hasText: 'A5-SKU' }).first().click()
      },
      action: '从商品事实生成草稿',
      expect: '尚无已批准版本',
      check: async (page) => {
        const history = await call(page, `/shops/${shop}/listings/versions`)
        expect(history.body.length).toBeGreaterThan(0)
        return { versions: history.body.length }
      },
    },
    {
      slug: 'inventory',
      path: '/inventory',
      label: '库存快照',
      action: '刷新库存',
      expect: 'A5-SKU',
    },
    {
      slug: 'profit',
      path: '/profit',
      label: '新品利润',
      prepare: async (page) => {
        await page.getByLabel('试算名称').first().fill('A5 利润试算')
        await page.getByLabel('方案名称').first().fill('A5 方案')
        await page.getByLabel('候选售价（USD / 件）').first().fill('20')
        await page.getByLabel('采购成本（USD / 件）').first().fill('18')
        await page.getByLabel('售价与采购成本依据').first().fill('安卓合成假设')
      },
      action: '计算并比较',
      region: '利润情景结果',
      check: async () => ({ assumptions: '售价 20 / 采购 18 / 合成依据' }),
    },
    {
      slug: 'product-quality',
      path: '/product-quality',
      label: '商品质量',
      action: '检查商品信息',
      region: '商品质量检查结果',
    },
    { slug: 'product-edits', path: '/product-edits', label: '商品修订', expect: '暂无修订记录' },
    { slug: 'support', path: '/support', label: '客服工作台', expect: 'A5-M1' },
    {
      slug: 'order-reconciliation',
      path: '/order-reconciliation',
      label: '订单销售与退款核对',
      action: '读取销售与退款待核清单',
      region: '订单金额待核清单',
    },
    {
      slug: 'analytics',
      path: '/analytics',
      label: '经营分析',
      action: '计算并查看证据',
      region: '分析结果',
      expect: '60.0000',
    },
    {
      slug: 'overview',
      path: '/overview',
      label: '经营总览',
      expandDetails: true,
      action: '生成经营总览',
      expect: '净销售额',
    },
    { slug: 'expenses', path: '/expenses', label: '实际费用', expect: '暂无已加载记录。' },
    { slug: 'statements', path: '/statements', label: '账单核对', expect: '读取并核对' },
    { slug: 'settlements', path: '/settlements', label: '结算与回款', region: '结算登记' },
    { slug: 'settings', path: '/settings', label: '经营资料', expect: shopName },
    { slug: 'rules', path: '/rules', label: '经营规则', region: '规则范围' },
    { slug: 'outbound', path: '/outbound', label: '测试外发', expect: '尚未配置' },
    { slug: 'schedules', path: '/schedules', label: '定时与通知', expect: '还没有定时计划。' },
  ]

  for (const spec of specs) {
    const onRoute = await ensureRoute(page, spec.path)
    expect(onRoute, `route ${spec.path} did not stay active`).toBe(true)
    await expandSections(page)
    const selected = await selectShop(page, shop)
    if (selected) await page.waitForTimeout(1200)
    const identity = await selectIdentity(page)
    if (spec.expandDetails) {
      await expandSections(page)
    }
    if (spec.expand) {
      const summary = page.getByText(spec.expand, { exact: true }).first()
      if ((await summary.count()) > 0) await summary.click()
    }
    if (spec.prepare) {
      await spec.prepare(page)
    }
    if (spec.action) {
      const button = page.getByRole('button', { name: spec.action }).first()
      await expect(button).toBeEnabled({ timeout: 60000 })
      await button.click()
    }
    if (spec.region) {
      await expect(page.getByRole('region', { name: spec.region }).first()).toBeVisible({
        timeout: 90000,
      })
    }
    if (spec.expect) {
      await expect(page.getByText(spec.expect, { exact: false }).first()).toBeVisible({
        timeout: 90000,
      })
    }
    const geometry = await page.evaluate(() => ({
      width: window.innerWidth,
      content: document.documentElement.scrollWidth,
    }))
    expect(geometry.content).toBeLessThanOrEqual(geometry.width + 1)
    const extra = spec.check ? await spec.check(page) : {}
    await shot(`a5-${spec.slug}`)
    record(`module:${spec.label}`, {
      path: spec.path,
      shop_selected: selected,
      synthetic_identity: identity,
      evidence: spec.expect ?? spec.region,
      ...geometry,
      ...extra,
    })
  }

  const status = await call(page, '/shops')
  record('module-scope-summary', {
    shop,
    shops: status.body.length,
    modules: specs.length,
  })
} catch (error) {
  results.push({ check: 'failure', passed: false, message: String(error) })
  if (active?.page) {
    console.log(await active.page.locator('body').innerText().catch(() => ''))
    await shot('a5-modules-failure').catch(() => {})
  }
  process.exitCode = 1
} finally {
  if (active?.browser) await active.browser.close().catch(() => {})
  await writeFile(
    path.join(output, 'device-a5-modules.json'),
    JSON.stringify({ serial, results }, null, 2),
  )
  console.log(JSON.stringify(results, null, 2))
}
