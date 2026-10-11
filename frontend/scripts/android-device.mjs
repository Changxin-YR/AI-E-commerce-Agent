/* global setTimeout, fetch */
import { chromium, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

export const root = path.resolve(import.meta.dirname, '../..')
export const output = path.join(root, '.local/android/evidence')
const adb = path.join(root, '.local/android/sdk/platform-tools/adb.exe')
// Business acceptance is restricted to the dedicated disposable Android AVD.
export const serial = 'emulator-5580'
const app = 'com.soloops.android'
export const run = (...args) => execFileSync(adb, ['-s', serial, ...args], { encoding: 'utf8' }).trim()
export async function shot(name) {
  await mkdir(output, { recursive: true })
  await writeFile(path.join(output, `${name}.png`), execFileSync(adb, ['-s', serial, 'exec-out', 'screencap', '-p']))
}
export async function connect() {
  for (let attempt = 0; attempt < 30; attempt++) {
    try {
      const pid = run('shell', 'pidof', app)
      run('forward', 'tcp:9223', `localabstract:webview_devtools_remote_${pid}`)
      const browser = await chromium.connectOverCDP('http://127.0.0.1:9223', { noDefaults: true })
      const page = browser.contexts()[0]?.pages()[0]
      if (page) return { browser, page }
      await browser.close()
    } catch { /* Wait for the installed WebView to start. */ }
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  throw new Error('Dedicated Android WebView unavailable')
}
export async function restart() {
  run('shell', 'am', 'force-stop', app)
  run('shell', 'am', 'start', '-n', `${app}/.MainActivity`)
  return connect()
}
export async function login(page) {
  await expect(page.locator('#username, .android-toolbar')).toBeVisible({ timeout: 30000 })
  if (await page.locator('#username').isVisible()) {
    await page.locator('#username').fill('android_seller')
    await page.locator('#password').fill('Android-Synthetic-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
  }
  await expect(page.locator('.android-toolbar')).toBeVisible({ timeout: 30000 })
}
export async function navigate(page, url) {
  if (!(await page.locator('.sidebar').isVisible())) await page.getByRole('button', { name: '全部功能', exact: true }).click()
  const expand = page.getByRole('button', { name: '展开全部功能', exact: false })
  if (await expand.isVisible()) await expand.click()
  await page.locator(`.seller-navigation a[href="${url}"]`).click()
  await expect(page).toHaveURL(new RegExp(`${url === '/' ? '/$' : url + '(\\?|$)'}`))
  await expect(page.locator('main h1')).toBeVisible()
}
export async function api(page, route, data) {
  const result = await page.evaluate(async ({ route, data }) => {
    const base = 'http://10.0.2.2:8011/api'
    const session = await (await fetch(`${base}/auth/session`)).json()
    const response = await fetch(base + route, data === undefined ? {} : {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-SoloOps-Client': 'web', 'X-CSRF-Token': session.csrf_token }, body: JSON.stringify(data),
    })
    return { status: response.status, body: await response.json() }
  }, { route, data })
  expect(result.status, JSON.stringify(result.body)).toBeLessThan(300)
  return result.body
}
export function hierarchy() {
  run('shell', 'uiautomator', 'dump', '/sdcard/soloops-a3-window.xml')
  return run('shell', 'cat', '/sdcard/soloops-a3-window.xml')
}
export function tapNode(xml, text) {
  const nodes = xml.match(/<node\b[^>]+>/g) ?? []
  const node = nodes.find((item) => {
    const label = /(?:text|content-desc)="([^"]*)"/.exec(item)?.[1] ?? ''
    return label.length > 0 && (label === text || label.includes(text))
  })
  if (!node) throw new Error(`Native node not found: ${text}\n${xml}`)
  const bounds = /bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/.exec(node)
  if (!bounds) throw new Error(`Native node has no bounds: ${text}`)
  run('shell', 'input', 'tap', String(Math.round((+bounds[1] + +bounds[3]) / 2)), String(Math.round((+bounds[2] + +bounds[4]) / 2)))
}
export async function chooseFile(page, label, filename) {
  await page.getByLabel(label, { exact: true }).click()
  let xml = hierarchy()
  expect(xml).toContain('com.google.android.documentsui')
  if (!xml.includes(`text="${filename}"`)) {
    tapNode(xml, 'Show roots')
    xml = hierarchy()
    tapNode(xml, 'Downloads')
    xml = hierarchy()
  }
  await shot('a3-native-picker')
  tapNode(xml, filename.replace(/\.csv$/, '').slice(0, 16))
}
