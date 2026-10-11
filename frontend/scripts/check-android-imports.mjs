/* global process, console */
import { expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { createHash } from 'node:crypto'
import { output, serial, run, restart, login, navigate, api, chooseFile, shot } from './android-device.mjs'

const results = []
const record = (check, evidence = {}) => { results.push({ check, passed: true, ...evidence }); console.log(check) }
let active
await mkdir(output, { recursive: true })
try {
  active = await restart()
  let { page } = active
  await login(page)
  await navigate(page, '/settings')
  await page.getByRole('button', { name: '添加店铺', exact: true }).click()
  const name = `安卓合成 A3 ${Date.now()}`
  await page.getByLabel('店铺名称', { exact: true }).fill(name)
  await page.getByLabel('店铺标识', { exact: true }).fill(`android-a3-${Date.now()}`)
  await page.getByRole('button', { name: '全部功能', exact: true }).click()
  await page.locator('.seller-navigation a[href="/imports"]').click()
  await expect(page.getByRole('dialog')).toBeVisible()
  console.log(await page.getByRole('dialog').innerText())
  await page.getByRole('button', { name: '继续编辑', exact: true }).click()
  await page.getByRole('button', { name: '确认添加', exact: true }).click()
  await expect(page.getByText(`店铺“${name}”已添加，当前使用文件模式。`)).toBeVisible()
  const shop = (await api(page, '/shops')).find((item) => item.name === name)
  await navigate(page, '/imports')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByLabel('所属店铺').selectOption(String(shop.id))
  await page.getByLabel('数据身份').selectOption('synthetic')
  record('shop-unsaved-protection-and-saved-navigation', { shop: shop.id })
  const csv = 'sku,name,unit_cost,cost_currency,facts\r\nA3-SKU,安卓合成商品,1,USD,"颜色蓝色，测试含逗号,与换行\n第二行"\r\n'
  const filename = 'soloops-a3-products.csv'
  const local = path.join(output, filename)
  await writeFile(local, csv)
  run('push', local, `/sdcard/Download/${filename}`)
  await chooseFile(page, 'CSV / Excel 文件', filename)
  await expect(page.getByRole('button', { name: '上传并查看映射' })).toBeEnabled()
  await page.getByRole('button', { name: '上传并查看映射' }).click()
  await expect(page.getByRole('heading', { name: '02 / 核对字段映射' })).toBeVisible({ timeout: 30000 })
  await page.getByRole('button', { name: '校验并预览' }).click()
  await page.getByRole('button', { name: '确认导入', exact: true }).click()
  await expect(page.getByText('批次已导入。可展开源行核对，重复确认不会重复增加业务记录。')).toBeVisible()
  const batches = await api(page, `/shops/${shop.id}/imports`)
  const batch = await api(page, `/imports/${batches[0].id}`)
  expect(batch.status).toBe('committed')
  expect(batch.rows[0].raw.name).toBe('安卓合成商品')
  expect(batch.rows[0].raw.facts).toBe('颜色蓝色，测试含逗号,与换行\n第二行')
  record('native-csv-byte-upload-and-source-readback', { batch: batch.id, sha256: createHash('sha256').update(csv).digest('hex') })
  await shot('a3-imported-products')
  await page.getByLabel('报表类型').selectOption('orders')
  const largeName = 'soloops-a3-orders.csv'
  const row = (i) => `A3-${i},1,A3-SKU,1,2,USD,2026-10-07T00:00:00Z,paid,0,0\r\n`
  const large = '\ufefforder_id,line_id,sku,quantity,unit_price,currency,ordered_at,status,discount,refund\r\n' + Array.from({ length: 2001 }, (_, i) => row(i === 2000 ? 0 : i)).join('')
  const largePath = path.join(output, largeName)
  await writeFile(largePath, large)
  run('push', largePath, `/sdcard/Download/${largeName}`)
  const largeLabel = '选择原始大报表 CSV（本机拆分／恢复）'
  await chooseFile(page, largeLabel, largeName)
  await expect(page.getByText('本机文件已就绪：2001个源记录', { exact: false })).toBeVisible({ timeout: 30000 })
  await page.getByRole('button', { name: '按当前来源建立导入组' }).click()
  await expect(page.getByTestId('group-coverage')).toContainText('源记录 0/2001')
  const group = (await api(page, `/shops/${shop.id}/import-groups`))[0]
  expect(group.manifest.source_sha256).toBe(createHash('sha256').update(large).digest('hex'))
  expect(group.manifest.parts).toHaveLength(2)
  async function commitPart(part) {
    await page.getByRole('button', { name: `上传／恢复第 ${part} 片` }).click()
    await page.getByRole('button', { name: '校验并预览' }).click()
    await page.getByRole('button', { name: '确认导入', exact: true }).click()
    await expect(page.getByTestId('group-coverage')).toContainText(`已提交 ${part}/2`, { timeout: 30000 })
  }
  await commitPart(1)
  record('native-worker-split-and-first-part', { group: group.id, rows: 2001, parts: 2 })
  await active.browser.close()
  active = await restart()
  page = active.page
  await login(page)
  await navigate(page, '/imports')
  await page.getByLabel('所属店铺').selectOption(String(shop.id))
  await page.getByLabel('报表类型').selectOption('orders')
  await page.getByLabel('数据身份').selectOption('synthetic')
  await page.getByLabel('继续导入组').selectOption(String(group.id))
  await expect(page.getByTestId('group-coverage')).toContainText('已提交 1/2')
  await writeFile(largePath, large + row(99999))
  run('push', largePath, `/sdcard/Download/${largeName}`)
  await chooseFile(page, largeLabel, largeName)
  await expect(page.getByText('原文件与当前组的文件名、指纹或分片清单不一致。', { exact: false })).toBeVisible()
  await writeFile(largePath, large)
  run('push', largePath, `/sdcard/Download/${largeName}`)
  await chooseFile(page, largeLabel, largeName)
  await expect(page.getByText('本机文件已就绪：2001个源记录', { exact: false })).toBeVisible()
  await commitPart(2)
  await expect(page.getByTestId('group-coverage')).toContainText('分片全部完成')
  await expect(page.getByTestId('group-coverage')).toContainText('去重后 2000；跨片重叠 1')
  const before = await api(page, `/import-groups/${group.id}`)
  await page.getByRole('button', { name: '上传／恢复第 1 片' }).click()
  await expect(page.getByRole('heading', { name: `批次 #${before.batches.find((item) => item.group_part === 1).id} · part-001.csv` })).toBeVisible()
  expect(await api(page, `/import-groups/${group.id}`)).toEqual(before)
  const analysis = await api(page, `/shops/${shop.id}/analytics/calculate`, {
    start_at: '2026-10-07T00:00:00Z', end_at: '2026-10-08T00:00:00Z', timezone: 'UTC', currency: 'USD', data_identity: 'synthetic',
  })
  expect(Number(analysis.summary.sales)).toBe(4000)
  record('force-stop-resume-fingerprint-dedup-and-sales', { group: group.id, sales: analysis.summary.sales })
  await shot('a3-complete-group')
} catch (error) {
  results.push({ check: 'failure', passed: false, message: String(error) })
  if (active?.page) { console.log(await active.page.locator('body').innerText().catch(() => '')); await shot('a3-failure').catch(() => {}) }
  process.exitCode = 1
} finally {
  if (active?.browser) await active.browser.close().catch(() => {})
  await writeFile(path.join(output, 'device-imports.json'), JSON.stringify({ serial, results }, null, 2))
  console.log(JSON.stringify(results, null, 2))
}
