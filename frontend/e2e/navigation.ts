import { expect, type Page } from '@playwright/test'

export async function openNavigation(page: Page) {
  const nav = page.getByRole('navigation', { name: '主导航', includeHidden: true })
  await expect(nav).toBeAttached()
  const menu = page.getByRole('button', { name: '展开导航菜单', exact: true })
  if (await menu.isVisible()) await menu.click()
  await expect(nav).toBeVisible()
  return page.getByRole('navigation', { name: '主导航' })
}
