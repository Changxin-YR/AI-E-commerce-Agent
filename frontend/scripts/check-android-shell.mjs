/* global process, setTimeout, document, window, console, getComputedStyle */
import { chromium, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '../..')
const output = path.join(root, '.local/android/evidence')
const adb = path.join(root, '.local/android/sdk/platform-tools/adb.exe')
const serial = process.env.SOLOOPS_ANDROID_SERIAL ?? 'emulator-5580'
const app = 'com.soloops.android'
const run = (...args) => execFileSync(adb, ['-s', serial, ...args], { encoding: 'utf8' }).trim()
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const results = []
let browser, page
const record = (check, evidence = {}) => results.push({ check, passed: true, ...evidence })
await mkdir(output, { recursive: true })
const saved = Object.fromEntries(
  ['accelerometer_rotation', 'user_rotation'].map((key) => [
    key,
    run('shell', 'settings', 'get', 'system', key),
  ]),
)
const keyboardSetting = run('shell', 'settings', 'get', 'secure', 'show_ime_with_hard_keyboard')
async function shot(name) {
  await writeFile(
    path.join(output, `a2-${name}.png`),
    execFileSync(adb, ['-s', serial, 'exec-out', 'screencap', '-p']),
  )
}
async function navigate(url) {
  await page.getByRole('button', { name: '全部功能', exact: true }).click()
  const expand = page.getByRole('button', { name: '展开全部功能', exact: false })
  if (await expand.isVisible()) await expand.click()
  await page.locator(`.seller-navigation a[href="${url}"]`).click()
  await expect(page).toHaveURL(new RegExp(`${url === '/' ? '/$' : url + '$'}`))
  await expect(page.locator('main h1')).toBeVisible()
}
try {
  run('shell', 'am', 'force-stop', app)
  run('shell', 'am', 'start', '-n', `${app}/.MainActivity`)
  for (let attempt = 0; attempt < 120; attempt++) {
    try {
      const pid = run('shell', 'pidof', app)
      run('forward', 'tcp:9223', `localabstract:webview_devtools_remote_${pid}`)
      browser = await chromium.connectOverCDP('http://127.0.0.1:9223', { noDefaults: true })
      page = browser.contexts()[0]?.pages()[0]
      if (page) break
      await browser.close()
    } catch {
      /* WebView may still be starting. */
    }
    await delay(1000)
  }
  expect(page).toBeTruthy()
  await expect(page.locator('#username, .android-toolbar')).toBeVisible({ timeout: 30000 })
  if (await page.locator('#username').isVisible()) {
    await expect(page.getByRole('button', { name: '进入工作台' })).toBeInViewport()
    await shot('login')
    record('login-submit-in-first-viewport')
    await page.locator('#username').fill('android_seller')
    await page.locator('#password').fill('Android-Synthetic-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
  }
  await expect(page.locator('.android-toolbar')).toBeVisible({ timeout: 30000 })
  await expect(page.locator('.sidebar')).toBeHidden()
  const insets = await page.evaluate(() => {
    const style = getComputedStyle(document.body)
    return {
      top: parseFloat(style.paddingTop),
      bottom: parseFloat(style.paddingBottom),
      pixelRatio: window.devicePixelRatio,
    }
  })
  // Older WebViews receive native window padding and intentionally zero CSS insets.
  run('shell', 'uiautomator', 'dump', '/sdcard/soloops-a2-window.xml')
  const hierarchy = run('shell', 'cat', '/sdcard/soloops-a2-window.xml')
  const bounds = /class="android.webkit.WebView"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/.exec(hierarchy)
  const screen = /Physical size: (\d+)x(\d+)/.exec(run('shell', 'wm', 'size'))
  expect(bounds, 'Native WebView bounds must be available').not.toBeNull()
  expect(screen, 'Physical display size must be available').not.toBeNull()
  const nativeTop = Number(bounds[2])
  const nativeBottom = Number(screen[2]) - Number(bounds[4])
  expect(insets.top).toBeGreaterThanOrEqual(0)
  expect(insets.bottom).toBeGreaterThanOrEqual(0)
  expect(nativeTop + insets.top * insets.pixelRatio).toBeGreaterThan(0)
  expect(nativeBottom + insets.bottom * insets.pixelRatio).toBeGreaterThan(0)
  record('system-bar-safe-area-padding', { ...insets, nativeTop, nativeBottom })
  await shot('home')
  await page.getByRole('button', { name: '全部功能', exact: true }).click()
  run('shell', 'input', 'keyevent', '4')
  await expect(page.locator('.sidebar')).toBeHidden()
  record('hardware-back-closes-navigation')

  const routes = [
    '/imports',
    '/agent',
    '/listings',
    '/inventory',
    '/profit',
    '/product-quality',
    '/product-edits',
    '/support',
    '/order-reconciliation',
    '/analytics',
    '/overview',
    '/expenses',
    '/statements',
    '/settlements',
    '/settings',
    '/rules',
    '/outbound',
    '/schedules',
    '/',
  ]
  for (const route of routes) {
    await navigate(route)
    const geometry = await page.evaluate(() => ({
      width: window.innerWidth,
      content: document.documentElement.scrollWidth,
    }))
    expect(geometry.content).toBeLessThanOrEqual(geometry.width + 1)
    record(`route:${route}`, { heading: await page.locator('main h1').innerText(), ...geometry })
  }
  await navigate('/settings')
  await expect(page.locator('#display-name')).toBeVisible({ timeout: 15000 })
  const originalName = await page.locator('#display-name').inputValue()
  await page.locator('#display-name').fill('A2 unsaved synthetic input')
  run('shell', 'input', 'keyevent', '4')
  // If the software keyboard was open, Android consumes the first back press.
  if (!(await page.getByRole('dialog').isVisible())) run('shell', 'input', 'keyevent', '4')
  await expect(page.getByRole('dialog')).toBeVisible()
  await shot('leave-protection')
  await page.getByRole('button', { name: '继续编辑', exact: true }).click()
  await expect(page.locator('#display-name')).toHaveValue('A2 unsaved synthetic input')
  record('hardware-back-keeps-unsaved-profile')

  run('shell', 'settings', 'put', 'secure', 'show_ime_with_hard_keyboard', '1')
  await page.locator('#display-name').click()
  await expect(page.locator('html')).toHaveClass(/keyboard-open/, { timeout: 10000 })
  await expect(page.locator('#display-name')).toBeInViewport()
  await shot('keyboard')
  run('shell', 'input', 'keyevent', '4')
  await expect(page.locator('html')).not.toHaveClass(/keyboard-open/)
  await expect(page).toHaveURL(/\/settings$/)
  record('keyboard-input-visible-back-hides-ime')

  run('shell', 'settings', 'put', 'system', 'accelerometer_rotation', '0')
  run('shell', 'settings', 'put', 'system', 'user_rotation', '1')
  await expect.poll(() => page.evaluate(() => window.innerWidth > window.innerHeight)).toBe(true)
  await expect(page.locator('#display-name')).toHaveValue('A2 unsaved synthetic input')
  await shot('landscape')
  run('shell', 'settings', 'put', 'system', 'user_rotation', '0')
  await expect.poll(() => page.evaluate(() => window.innerWidth < window.innerHeight)).toBe(true)
  record('rotation-retains-route-and-input')

  run('shell', 'input', 'keyevent', '3')
  await delay(800)
  run('shell', 'am', 'start', '-n', `${app}/.MainActivity`)
  await expect(page.locator('#display-name')).toHaveValue('A2 unsaved synthetic input')
  record('home-resume-retains-route-and-input')

  run('shell', 'svc', 'wifi', 'disable')
  run('shell', 'svc', 'data', 'disable')
  await expect(page.locator('.connection-notice')).toContainText(/无法连接|网络已断开/, {
    timeout: 15000,
  })
  await expect(page.locator('#display-name')).toHaveValue('A2 unsaved synthetic input')
  await shot('offline-input')
  await page.locator('#display-name').fill(originalName)
  await page.getByRole('button', { name: '关闭连接提示' }).click()
  await navigate('/')
  await navigate('/settings')
  await expect(page.getByRole('button', { name: '重新加载', exact: true })).toBeVisible({
    timeout: 30000,
  })
  record('offline-api-error-with-retry')
  run('shell', 'svc', 'wifi', 'enable')
  run('shell', 'svc', 'data', 'enable')
  await expect(page.locator('.connection-notice')).toContainText('连接已恢复', { timeout: 30000 })
  await page.getByRole('button', { name: '关闭连接提示' }).click()
  await page.getByRole('button', { name: '重新加载', exact: true }).click()
  await expect(page.locator('#display-name')).toBeVisible({ timeout: 15000 })
  await expect(page.locator('#display-name')).toHaveValue(originalName)
  await shot('recovered')
  record('network-restoration-and-explicit-read-retry')

  await page.locator('#display-name').fill('A2 discard input')
  await page.getByRole('button', { name: '全部功能', exact: true }).click()
  await page.getByRole('button', { name: '退出', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: '继续编辑', exact: true }).click()
  await expect(page.locator('#display-name')).toHaveValue('A2 discard input')
  await page.getByRole('button', { name: '退出', exact: true }).click()
  await page.getByRole('button', { name: '放弃并离开', exact: true }).click()
  await expect(page.locator('#username')).toBeVisible({ timeout: 15000 })
  record('logout-requires-unsaved-confirmation')
} catch (error) {
  results.push({ check: 'failure', passed: false, message: String(error) })
  await shot('failure').catch(() => {})
  process.exitCode = 1
} finally {
  run('shell', 'svc', 'wifi', 'enable')
  run('shell', 'svc', 'data', 'enable')
  for (const [key, value] of Object.entries(saved))
    run(
      'shell',
      'settings',
      value === 'null' ? 'delete' : 'put',
      'system',
      key,
      ...(value === 'null' ? [] : [value]),
    )
  run(
    'shell',
    'settings',
    keyboardSetting === 'null' ? 'delete' : 'put',
    'secure',
    'show_ime_with_hard_keyboard',
    ...(keyboardSetting === 'null' ? [] : [keyboardSetting]),
  )
  await browser?.close().catch(() => {})
  await writeFile(
    path.join(output, 'device-shell.json'),
    JSON.stringify({ serial, results }, null, 2),
  )
  console.log(JSON.stringify(results, null, 2))
}
