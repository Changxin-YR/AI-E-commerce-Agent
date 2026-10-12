/* global console, process, window */
import { expect } from '@playwright/test'
import { createHash } from 'node:crypto'
import { readFile, mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { output, serial, run, connect, login, shot } from './android-device.mjs'

// A6 device acceptance for installation and upgrade. Phase "baseline" installs the
// previous version and logs in; phase "upgrade" installs the rebuilt APK over it and
// proves the session survives; phase "release" installs the signed release APK as a
// clean install and expects the login screen.
const phase = process.env.SOLOOPS_PACKAGE_PHASE ?? 'upgrade'
const app = 'com.soloops.android'
const debugApk = path.join(
  path.resolve(import.meta.dirname, '../..'),
  'frontend/android/app/build/outputs/apk/debug/app-debug.apk',
)
const releaseApk = path.join(
  path.resolve(import.meta.dirname, '../..'),
  'frontend/android/app/build/outputs/apk/release/app-release.apk',
)
const apk = process.env.SOLOOPS_APK ?? (phase === 'release' ? releaseApk : debugApk)
const results = []
const record = (check, evidence = {}) => {
  results.push({ check, passed: true, ...evidence })
  console.log(check)
}
await mkdir(output, { recursive: true })

function installed() {
  const dump = run('shell', 'dumpsys', 'package', app)
  return {
    versionCode: Number(/versionCode=(\d+)/.exec(dump)?.[1] ?? 0),
    versionName: /versionName=([^\s]+)/.exec(dump)?.[1] ?? '',
  }
}

async function apkDigest(file) {
  const bytes = await readFile(file)
  return {
    file,
    bytes: bytes.length,
    sha256: createHash('sha256').update(bytes).digest('hex'),
  }
}

let active
try {
  const before = installed()
  const artifact = await apkDigest(apk)
  console.log('installed before', JSON.stringify(before))
  if (phase === 'release') {
    run('uninstall', app)
  }
  const install = run('install', '-r', apk)
  expect(install).toContain('Success')
  const after = installed()
  if (phase === 'upgrade') {
    // Only an in-place upgrade must prove the version actually moved forward.
    expect(after.versionCode).toBeGreaterThan(before.versionCode)
  }
  run('shell', 'am', 'start', '-n', `${app}/.MainActivity`)
  active = await connect()
  if (phase === 'release') {
    // A clean signed install must start at the login screen.
    await expect(active.page.locator('#username')).toBeVisible({ timeout: 60000 })
    await expect(active.page.locator('.android-toolbar')).toBeHidden()
    record('release-clean-install-shows-login', { before, after, ...artifact })
  } else if (phase === 'baseline') {
    await expect(active.page.locator('#username')).toBeVisible({ timeout: 60000 })
    await login(active.page)
    record('baseline-install-and-login', { before, after, ...artifact })
  } else {
    // An in-place upgrade must keep the existing session and route.
    await expect(active.page.locator('.android-toolbar')).toBeVisible({ timeout: 60000 })
    record('upgrade-preserves-session', {
      before,
      after,
      ...artifact,
      route: await active.page.evaluate(() => window.location.pathname),
    })
  }
  await shot(`a6-${phase}`)
} catch (error) {
  results.push({ check: 'failure', passed: false, message: String(error) })
  if (active?.page) {
    console.log(await active.page.locator('body').innerText().catch(() => ''))
    await shot(`a6-${phase}-failure`).catch(() => {})
  }
  process.exitCode = 1
} finally {
  if (active?.browser) await active.browser.close().catch(() => {})
  await writeFile(
    path.join(output, `device-a6-${phase}.json`),
    JSON.stringify({ serial, phase, apk, results }, null, 2),
  )
  console.log(JSON.stringify(results, null, 2))
}
