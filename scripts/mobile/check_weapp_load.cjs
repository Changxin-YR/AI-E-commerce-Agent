// Checks the seller startup page through WeChat's local automation SDK.
const assert = require('node:assert/strict')
const path = require('node:path')
const root = path.resolve(__dirname, '../..')
const automator = require(path.join(root, '.local/weapp-tools/node_modules/miniprogram-automator'))

let miniProgram
const deadline = setTimeout(() => {
  console.error('FAIL: WeChat startup page verification timed out after 55 seconds')
  miniProgram?.disconnect()
  process.exit(1)
}, 55000)

async function main() {
  miniProgram = await automator.connect({ wsEndpoint: 'ws://127.0.0.1:9420' })
  const page = await miniProgram.currentPage()
  assert.equal(page?.path, 'pages/index/index', 'Expected SoloOps startup route')
  const title = await page.$('.title')
  assert.ok(title, 'Startup title must exist')
  assert.equal(await title.text(), '经营有据，行动有序。')
  const brand = await page.$('.eyebrow')
  assert.ok(brand, 'Seller workspace brand must exist')
  assert.match(await brand.text(), /SOLOOPS.*卖家工作台/)
  console.log(JSON.stringify({ status: 'PASS', route: page.path, title: '经营有据，行动有序。',
    scope: 'IDE startup page loaded; no business actions, account login or publication' }))
}

main().catch(error => {
  console.error(`FAIL: ${error.message}`)
  process.exitCode = 1
}).finally(() => {
  clearTimeout(deadline)
  miniProgram?.disconnect()
})
