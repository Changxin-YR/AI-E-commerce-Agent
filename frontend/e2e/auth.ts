import { expect, type Page } from '@playwright/test'

export async function signIn(
  page: Page,
  destination = '/',
  username = 'e2e_seller',
): Promise<void> {
  await page.goto(destination)
  await page.getByLabel('账号', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill('Synthetic-E2E-Password-2026!')
  await page.getByRole('button', { name: '进入工作台', exact: true }).click()
  const target = new URL(destination, page.url())
  const expected = target.pathname === '/login' ? '/' : target.pathname
  await expect(page).toHaveURL(
    (url) =>
      url.pathname === expected &&
      (target.pathname === '/login' || (url.search === target.search && url.hash === target.hash)),
  )
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
}
