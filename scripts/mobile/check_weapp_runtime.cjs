// Verifies the mini program against the loopback acceptance API through WeChat's
// local automation SDK: login, a list read and one real write. Synthetic data only.
const path = require('node:path')
const root = path.resolve(__dirname, '../..')
const automator = require(path.join(root, '.local/weapp-tools/node_modules/miniprogram-automator'))

const WS = 'ws://127.0.0.1:9420'
const USER = 'harmony_r2'
const PASSWORD = 'Synthetic-R2-2026!'
const steps = []
const failures = []

const record = (name, data) => steps.push({ name, ...data })

async function textOf(page, selector) {
  const element = await page.$(selector)
  return element === null ? null : (await element.text()).trim()
}

async function tapLabel(page, label) {
  const buttons = await page.$$('.action')
  for (const button of buttons) {
    if ((await button.text()).trim() === label) {
      await button.tap()
      return true
    }
  }
  return false
}

async function main() {
  const program = await automator.connect({ wsEndpoint: WS })
  let page = await program.currentPage()
  record('start', { route: page.path, title: await textOf(page, '.shell__title') })

  // 1) 登录：POST /api/mobile/auth/login，成功后应用会切到首页
  const inputs = await page.$$('.field__input')
  if (inputs.length < 2) throw new Error(`login inputs missing: ${inputs.length}`)
  await inputs[0].input(USER)
  await inputs[1].input(PASSWORD)
  const tapped = await tapLabel(page, '登录')
  if (!tapped) throw new Error('login button not found')
  await page.waitFor(5000)
  page = await program.currentPage()
  record('afterLogin', {
    route: page.path,
    title: await textOf(page, '.shell__title'),
    error: await textOf(page, '.shell__error-text'),
  })

  // 2) 列表读取：待办页（GET /workbench + operations/tasks）
  await program.switchTab('/pages/tasks/index')
  await page.waitFor(3500)
  page = await program.currentPage()
  const taskTitles = []
  for (const card of await page.$$('.card')) {
    const text = (await card.text()).trim()
    if (text !== '') taskTitles.push(text.slice(0, 40))
  }
  record('tasks', { route: page.path, cards: taskTitles.length, sample: taskTitles.slice(0, 3) })

  // 3) 真实写操作：商品质量检查 → 保存质量报告（POST /product-quality/reports）
  await program.navigateTo('/pages/product_quality/index')
  await page.waitFor(3000)
  page = await program.currentPage()
  record('qualityOpen', { route: page.path, title: await textOf(page, '.shell__title') })

  if (!(await tapLabel(page, '检查当前商品'))) throw new Error('check button not found')
  await page.waitFor(4000)
  const facts = []
  for (const line of await page.$$('.fact')) {
    const text = (await line.text()).trim()
    if (text !== '') facts.push(text.replace(/\s+/g, ' ').slice(0, 60))
  }
  record('qualityPreview', { facts: facts.slice(0, 8) })

  const confirmCard = await page.$('.card')
  if (confirmCard !== null) await confirmCard.tap()
  await page.waitFor(600)
  const saved = await tapLabel(page, '保存质量报告')
  await page.waitFor(4000)
  record('qualitySaved', {
    tappedSave: saved,
    success: await textOf(page, '.shell__success-text'),
    error: await textOf(page, '.shell__error-text'),
    notice: await textOf(page, '.shell__notice-text'),
  })

  await program.disconnect()
}

main()
  .catch((error) => failures.push(`${error.message}`))
  .finally(() => {
    console.log(JSON.stringify({ steps, failures }, null, 1))
    process.exitCode = failures.length === 0 ? 0 : 1
  })
