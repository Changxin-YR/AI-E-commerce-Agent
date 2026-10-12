/* global console, process, window, document, getComputedStyle */
import { expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import {
  output,
  serial,
  run,
  connect,
  login,
  navigate,
  shot,
} from './android-device.mjs'

// A5 device adaptation: the installed APK is exercised at a small-phone size, a
// tablet-ish size, landscape and a larger system font. Every configuration must
// keep each entry reachable without horizontal overflow.
const app = 'com.soloops.android'
const routes = [
  '/',
  '/imports',
  '/agent',
  '/listings',
  '/support',
  '/analytics',
  '/settings',
  '/schedules',
]
const results = []
const record = (check, evidence = {}) => {
  results.push({ check, passed: true, ...evidence })
  console.log(check)
}
await mkdir(output, { recursive: true })
const saved = {
  size: run('shell', 'wm', 'size'),
  density: run('shell', 'wm', 'density'),
  font: run('shell', 'settings', 'get', 'system', 'font_scale'),
  rotation: run('shell', 'settings', 'get', 'system', 'user_rotation'),
  autoRotate: run('shell', 'settings', 'get', 'system', 'accelerometer_rotation'),
}
console.log('saved', JSON.stringify(saved))

async function restartApp() {
  run('shell', 'am', 'force-stop', app)
  run('shell', 'am', 'start', '-n', `${app}/.MainActivity`)
  const active = await connect()
  await login(active.page)
  return active
}

async function sweep(page, label) {
  for (const route of routes) {
    await navigate(page, route)
    await expect(page.locator('.android-toolbar')).toBeVisible({ timeout: 30000 })
    const geometry = await page.evaluate(() => ({
      width: window.innerWidth,
      height: window.innerHeight,
      content: document.documentElement.scrollWidth,
      headingSize: getComputedStyle(document.querySelector('main h1')).fontSize,
    }))
    expect(
      geometry.content,
      `${label} ${route}: document scrollWidth ${geometry.content} > viewport ${geometry.width}`,
    ).toBeLessThanOrEqual(geometry.width + 1)
    record(`adapt:${label}:${route}`, {
      heading: await page.locator('main h1').innerText(),
      ...geometry,
    })
  }
}

let active
try {
  active = await restartApp()
  await sweep(active.page, 'default')
  await shot('a5-default-dashboard')

  run('shell', 'wm', 'size', '720x1280')
  run('shell', 'wm', 'density', '320')
  active.browser.close().catch(() => {})
  active = await restartApp()
  await expect
    .poll(() => active.page.evaluate(() => window.innerWidth))
    .toBeLessThanOrEqual(720)
  await sweep(active.page, 'small-720x1280')
  await shot('a5-small-phone')

  run('shell', 'wm', 'size', '1600x2560')
  run('shell', 'wm', 'density', '240')
  active.browser.close().catch(() => {})
  active = await restartApp()
  await expect
    .poll(() => active.page.evaluate(() => window.innerWidth))
    .toBeGreaterThanOrEqual(1000)
  await sweep(active.page, 'tablet-1600x2560')
  await shot('a5-tablet')

  run('shell', 'wm', 'size', 'reset')
  run('shell', 'wm', 'density', 'reset')
  run('shell', 'settings', 'put', 'system', 'accelerometer_rotation', '0')
  run('shell', 'settings', 'put', 'system', 'user_rotation', '1')
  active.browser.close().catch(() => {})
  active = await restartApp()
  await expect
    .poll(() => active.page.evaluate(() => window.innerWidth > window.innerHeight))
    .toBe(true)
  await sweep(active.page, 'landscape')
  await shot('a5-landscape')
  run('shell', 'settings', 'put', 'system', 'user_rotation', '0')

  const before = await active.page.evaluate(
    () => getComputedStyle(document.querySelector('main h1')).fontSize,
  )
  run('shell', 'settings', 'put', 'system', 'font_scale', '1.3')
  active.browser.close().catch(() => {})
  active = await restartApp()
  const after = await active.page.evaluate(
    () => getComputedStyle(document.querySelector('main h1')).fontSize,
  )
  await sweep(active.page, 'large-font-1.3')
  await shot('a5-large-font')
  record('adapt:font-scale-effect', {
    before,
    after,
    webview_follows_system_font_scale: before !== after,
  })
} catch (error) {
  results.push({ check: 'failure', passed: false, message: String(error) })
  if (active?.page) {
    console.log(await active.page.locator('body').innerText().catch(() => ''))
    await shot('a5-adaptation-failure').catch(() => {})
  }
  process.exitCode = 1
} finally {
  run('shell', 'wm', 'size', 'reset')
  run('shell', 'wm', 'density', 'reset')
  run(
    'shell',
    'settings',
    saved.font === 'null' ? 'delete' : 'put',
    'system',
    'font_scale',
    ...(saved.font === 'null' ? [] : [saved.font]),
  )
  run(
    'shell',
    'settings',
    saved.autoRotate === 'null' ? 'delete' : 'put',
    'system',
    'accelerometer_rotation',
    ...(saved.autoRotate === 'null' ? [] : [saved.autoRotate]),
  )
  run(
    'shell',
    'settings',
    saved.rotation === 'null' ? 'delete' : 'put',
    'system',
    'user_rotation',
    ...(saved.rotation === 'null' ? [] : [saved.rotation]),
  )
  if (active?.browser) await active.browser.close().catch(() => {})
  await writeFile(
    path.join(output, 'device-a5-adaptation.json'),
    JSON.stringify({ serial, routes, results }, null, 2),
  )
  console.log(JSON.stringify(results, null, 2))
}
