import { expect, test, type Page } from '@playwright/test'

async function login(page: Page): Promise<void> {
  await page.goto('/')
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('heading', { name: '把经营的第一步，准备好。' })).toBeVisible()
}

test('anonymous users must log in and invalid credentials remain on the login page', async ({
  page,
}) => {
  await page.goto('/settings')
  await expect(page).toHaveURL(/\/login$/)
  await page.getByLabel('账号', { exact: true }).fill('e2e_seller')
  await page.getByLabel('密码', { exact: true }).fill('incorrect-password')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page.getByRole('alert')).toContainText('账号或密码错误')
})

test('seller can save a profile, add a store, reload and revoke the session', async ({ page }) => {
  await login(page)
  await page.getByRole('link', { name: '完善经营资料' }).click()
  await page.getByLabel('经营名称').fill('合成 E2E 工作室')
  await page.getByLabel('经营模式').fill('自有品牌')
  await page.getByLabel('主营类目').fill('家居用品')
  await page.getByRole('button', { name: '保存经营资料' }).click()
  await expect(page.getByRole('status')).toContainText('经营资料已保存')
  await page.getByRole('button', { name: '添加店铺' }).click()
  await page.getByLabel('店铺名称').fill('合成 E2E 店铺')
  await page.getByLabel('店铺标识').fill('synthetic-e2e')
  await page.getByRole('button', { name: '确认添加' }).click()
  await expect(page.getByRole('heading', { name: '合成 E2E 店铺' })).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('经营名称')).toHaveValue('合成 E2E 工作室')
  await expect(page.getByText('文件模式', { exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/workspace-desktop.png', fullPage: true })
  await page.getByRole('button', { name: '退出' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto('/settings')
  await expect(page).toHaveURL(/\/login$/)
})

test('mobile seller settings fit the viewport and preserve accessible inputs', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await login(page)
  await page
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: /经营资料/ })
    .click()
  await expect(page.getByLabel('经营名称')).toBeVisible()
  const overflows = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  )
  expect(overflows).toBe(false)
  await page.screenshot({ path: 'test-results/workspace-mobile.png', fullPage: true })
})
