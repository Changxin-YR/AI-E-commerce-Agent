// Checks the seller startup page through WeChat's local automation SDK.
//
// The SDK's page.$ and page.data calls hang against this Taro 4 + Vue 3 build:
// they wait for a page-data channel message the Taro page never sends. The
// app-level bridge stays healthy, so this check asserts through it:
//   1. currentPage() reports the expected route,
//   2. miniProgram.evaluate() reads the route from the running appservice,
//   3. screenshot() returns a valid PNG of the simulator at the expected size.
// Run it after the simulator is up (see docs/mobile/weapp-ide-acceptance-log.md).
const assert = require('node:assert/strict')
const path = require('node:path')
const { writeFileSync } = require('node:fs')
const root = path.resolve(__dirname, '../..')
const automator = require(
  path.join(root, '.local/weapp-tools/node_modules/miniprogram-automator'),
)

let miniProgram
const deadline = setTimeout(() => {
  console.error(
    'FAIL: WeChat startup page verification timed out after 55 seconds',
  )
  miniProgram?.disconnect()
  process.exit(1)
}, 55000)

function pngSize(buffer) {
  const signature = Buffer.from([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
  ])
  if (!buffer.subarray(0, 8).equals(signature)) return null
  if (buffer.subarray(12, 16).toString('ascii') !== 'IHDR') return null
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) }
}

async function main() {
  miniProgram = await automator.connect({ wsEndpoint: 'ws://127.0.0.1:9420' })
  const page = await miniProgram.currentPage()
  assert.equal(
    page?.path,
    'pages/index/index',
    'Expected SoloOps startup route',
  )
  const route = await miniProgram.evaluate(function () {
    const stack = getCurrentPages()
    return String(stack[stack.length - 1].route)
  })
  assert.equal(
    route,
    'pages/index/index',
    'Running appservice must report the startup route',
  )
  const base64 = await miniProgram.screenshot()
  assert.equal(
    typeof base64,
    'string',
    'Simulator screenshot must return PNG data',
  )
  const buffer = Buffer.from(base64, 'base64')
  assert.ok(
    buffer.length > 10000,
    `Screenshot looks empty (${buffer.length} bytes)`,
  )
  const size = pngSize(buffer)
  assert.ok(size, 'Screenshot must be a PNG image')
  assert.ok(
    size.width >= 320 && size.height >= 480,
    `Screenshot size ${size.width}x${size.height} is too small for a rendered page`,
  )
  const target = process.env.SOLOOPS_WEAPP_SHOT
  if (target) writeFileSync(target, buffer)
  console.log(
    JSON.stringify({
      status: 'PASS',
      route,
      screenshot: {
        width: size.width,
        height: size.height,
        bytes: buffer.length,
      },
      scope:
        'IDE startup page loaded and rendered; no business actions, account login or publication',
    }),
  )
}

main()
  .catch((error) => {
    console.error(`FAIL: ${error.message}`)
    process.exitCode = 1
  })
  .finally(() => {
    clearTimeout(deadline)
    miniProgram?.disconnect()
  })
