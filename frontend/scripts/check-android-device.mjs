/* global process, setTimeout, fetch, document, console */
import { chromium, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '../..')
const output = path.join(root, '.local/android/evidence')
const adb = path.join(root, '.local/android/sdk/platform-tools/adb.exe')
const serial = process.env.SOLOOPS_ANDROID_SERIAL ?? 'emulator-5580'
const app = 'com.soloops.android'
const results = []
const runAdb = (...args) => execFileSync(adb, ['-s', serial, ...args], { encoding: 'utf8' }).trim()
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
await mkdir(output, { recursive: true })

async function connect() {
  let lastError
  for (let attempt = 0; attempt < 120; attempt++) {
    try {
      const pid = runAdb('shell', 'pidof', app)
      if (pid) {
        runAdb('forward', 'tcp:9223', `localabstract:webview_devtools_remote_${pid}`)
        const browser = await chromium.connectOverCDP('http://127.0.0.1:9223', { noDefaults: true })
        const page = browser.contexts()[0]?.pages()[0]
        if (page) return { browser, page }
        await browser.close()
      }
    } catch (error) {
      lastError = error
    }
    await delay(1000)
  }
  throw new Error(`Android WebView did not become available: ${lastError}`)
}

async function restart() {
  runAdb('shell', 'am', 'force-stop', app)
  runAdb('shell', 'am', 'start', '-n', `${app}/.MainActivity`)
  return connect()
}

let active
try {
  runAdb('shell', 'pm', 'clear', app)
  active = await restart()
  let { page } = active
  await expect(page.locator('#username')).toBeVisible({ timeout: 30000 })
  results.push({ check: 'fresh-install-login-screen', passed: true })
  await page.locator('#username').fill('android_seller')
  await page.locator('#password').fill('Wrong-Synthetic-Password!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.locator('.feedback')).toBeVisible({ timeout: 15000 })
  results.push({
    check: 'wrong-password-feedback',
    passed: true,
    text: await page.locator('.feedback').innerText(),
  })
  await page.locator('#password').fill('Android-Synthetic-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.locator('.account-row')).toContainText('android_seller', { timeout: 15000 })
  await page.screenshot({ path: path.join(output, 'logged-in.png') })
  results.push({ check: 'ui-login', passed: true })

  const security = await page.evaluate(async () => {
    const base = 'http://10.0.2.2:8011/api'
    const session = await fetch(`${base}/auth/session`)
    const sessionData = await session.json()
    const attempts = []
    for (const token of ['', 'invalid']) {
      const response = await fetch(`${base}/auth/logout`, {
        method: 'POST',
        headers: { 'X-SoloOps-Client': 'web', 'X-CSRF-Token': token },
      })
      attempts.push({ status: response.status, code: (await response.json()).error?.code })
    }
    return {
      sessionStatus: session.status,
      username: sessionData.username,
      attempts,
      documentCookie: document.cookie,
    }
  })
  expect(security.sessionStatus).toBe(200)
  expect(security.username).toBe('android_seller')
  expect(security.attempts).toEqual([
    { status: 403, code: 'csrf_rejected' },
    { status: 403, code: 'csrf_rejected' },
  ])
  expect(security.documentCookie).not.toContain('soloops_session')
  results.push({ check: 'device-session-and-csrf', passed: true, ...security })
  await active.browser.close()
  active = await restart()
  page = active.page
  await expect(page.locator('.account-row')).toContainText('android_seller', { timeout: 30000 })
  results.push({ check: 'force-stop-session-restoration', passed: true })
  await page.getByRole('button', { name: '全部功能', exact: true }).click()
  await page.getByRole('button', { name: '退出', exact: true }).click()
  await expect(page.locator('#username')).toBeVisible({ timeout: 15000 })
  const status = await page.evaluate(
    async () => (await fetch('http://10.0.2.2:8011/api/auth/session')).status,
  )
  expect(status).toBe(401)
  results.push({ check: 'ui-logout-revokes-session', passed: true })
  await active.browser.close()
  active = await restart()
  await expect(active.page.locator('#username')).toBeVisible({ timeout: 30000 })
  results.push({ check: 'logged-out-after-restart', passed: true })
  await active.page.screenshot({ path: path.join(output, 'logged-out.png') })
} catch (error) {
  results.push({ check: 'failure', passed: false, message: String(error) })
  if (active?.page)
    await active.page
      .screenshot({ path: path.join(output, 'failure.png') })
      .catch(() => {})
  process.exitCode = 1
} finally {
  if (active?.browser) await active.browser.close().catch(() => {})
  await writeFile(
    path.join(output, 'device-auth.json'),
    JSON.stringify({ serial, results }, null, 2),
  )
  console.log(JSON.stringify(results, null, 2))
}
