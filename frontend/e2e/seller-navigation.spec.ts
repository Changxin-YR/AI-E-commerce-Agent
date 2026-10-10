import { expect, test } from '@playwright/test'
import { tmpdir } from 'node:os'
import path from 'node:path'

for (const width of [1440, 390]) {
  test(`seller can reach all 19 grouped routes with keyboard at ${width}px`, async ({ page }) => {
    test.setTimeout(90000)
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/')
    await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
    await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
    await page.getByRole('button', { name: '进入工作台' }).click()
    const nav = page.getByRole('navigation', { name: '主导航' })
    await expect(nav.getByRole('button', { name: /今日 AI 运营/ })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    const expand = nav.getByRole('button', { name: '展开全部功能' })
    await expand.focus()
    await page.keyboard.press('Enter')
    await expect(nav.getByRole('link')).toHaveCount(19)
    const links = await nav
      .getByRole('link')
      .evaluateAll((nodes) =>
        nodes.map((n) => ({ label: n.textContent!, href: n.getAttribute('href')! })),
      )
    for (const link of links) {
      await nav.getByRole('link', { name: link.label, exact: true }).click()
      await expect(page).toHaveURL((url) => url.pathname === link.href)
      await expect(page.locator('main h1')).toBeVisible()
      await expect(nav.getByRole('link', { name: link.label, exact: true })).toHaveAttribute(
        'aria-current',
        'page',
      )
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
    }
    await nav.getByRole('button', { name: '收起全部功能' }).click()
    await expect(nav.getByRole('link')).toHaveCount(0)
    const orders = nav.getByRole('button', { name: /订单与客服/ })
    await orders.focus()
    await page.keyboard.press('Space')
    await expect(nav.getByRole('link', { name: '订单销售与退款核对' })).toBeVisible()
    await page.reload()
    await expect(nav.getByRole('button', { name: /自动化与设置/ })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    await page.screenshot({ path: path.join(tmpdir(), `soloops-a4-navigation-${width}.png`) })
  })
}
